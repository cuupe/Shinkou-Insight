package com.cuupe.backend.modules.evaluation.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.agent.mapper.AgentMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.evaluation.entity.EvaluationCase;
import com.cuupe.backend.modules.evaluation.mapper.EvaluationCaseMapper;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/workspaces/{workspaceId}/evaluation-cases")
@RequiredArgsConstructor
public class EvaluationCaseController {
    private static final int RETRIEVAL_TOP_K = 5;

    private final EvaluationCaseMapper mapper;
    private final NotificationService notificationService;
    private final AgentMapper accessMapper;
    private final AiIndexingClient aiClient;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final ObjectMapper objectMapper;

    @GetMapping
    public Result<List<EvaluationCase>> list(
            @PathVariable Long workspaceId,
            Authentication auth
    ) {
        return Result.success(mapper.findByWorkspace(workspaceId, userId(auth)));
    }

    @PostMapping
    public Result<EvaluationCase> create(
            @PathVariable Long workspaceId,
            @Valid @RequestBody CaseRequest request,
            Authentication auth
    ) {
        EvaluationCase item = new EvaluationCase();
        item.setWorkspaceId(workspaceId);
        item.setProjectId(request.projectId());
        item.setQuery(request.query().trim());
        item.setExpectedAnswer(trimToNull(request.expectedAnswer()));
        item.setExpectedAsset(normalizeExpectedAsset(request.expectedAsset()));
        item.setExpectedChunkIds(writeJson(normalizeValues(request.expectedChunkIds())));
        item.setRequiredFacts(writeJson(normalizeValues(request.requiredFacts())));
        item.setForbiddenFacts(writeJson(normalizeValues(request.forbiddenFacts())));
        item.setCreatedBy(userId(auth));
        mapper.insert(item);
        notificationService.create(
                workspaceId,
                userId(auth),
                request.projectId(),
                "evaluation",
                "评估用例已创建",
                "新的评估用例已加入评估集。",
                "project-evaluation"
        );
        return Result.success(mapper.findById(workspaceId, item.getId(), userId(auth)));
    }

    @PatchMapping("/{caseId}")
    public Result<EvaluationCase> update(
            @PathVariable Long workspaceId,
            @PathVariable Long caseId,
            @RequestBody Map<String, Object> body,
            Authentication auth
    ) {
        Long userId = userId(auth);
        EvaluationCase item = required(workspaceId, caseId, userId);
        if (containsDefinition(body)) {
            if (body.containsKey("query")) {
                String query = stringValue(body.get("query")).trim();
                if (query.isBlank()) {
                    throw invalid("评估问题不能为空");
                }
                item.setQuery(query);
            }
            if (body.containsKey("expectedAnswer")) item.setExpectedAnswer(trimToNull(stringValue(body.get("expectedAnswer"))));
            if (body.containsKey("expectedAsset")) item.setExpectedAsset(normalizeExpectedAsset(stringValue(body.get("expectedAsset"))));
            if (body.containsKey("expectedChunkIds")) item.setExpectedChunkIds(writeJson(normalizeValues(body.get("expectedChunkIds"))));
            if (body.containsKey("requiredFacts")) item.setRequiredFacts(writeJson(normalizeValues(body.get("requiredFacts"))));
            if (body.containsKey("forbiddenFacts")) item.setForbiddenFacts(writeJson(normalizeValues(body.get("forbiddenFacts"))));
            item.setCreatedBy(userId);
            mapper.updateDefinition(item);
        }

        if (body.containsKey("status")) {
            String status = normalizeStatus(body.get("status"));
            if (mapper.updateStatus(workspaceId, caseId, userId, status) == 0) {
                throw notFound();
            }
        }
        return Result.success(required(workspaceId, caseId, userId));
    }

    @PostMapping("/{caseId}/run")
    public Result<EvaluationCase> runRetrievalEvaluation(
            @PathVariable Long workspaceId,
            @PathVariable Long caseId,
            Authentication auth
    ) throws IOException {
        Long userId = userId(auth);
        EvaluationCase item = required(workspaceId, caseId, userId);
        if (item.getProjectId() == null) {
            throw invalid("此用例尚未绑定项目，请先在项目中重新建立或标注用例。");
        }
        if (!accessMapper.hasProjectAccess(workspaceId, item.getProjectId(), userId)) {
            throw notFound();
        }

        List<String> expectedChunkIds = readJsonArray(item.getExpectedChunkIds());
        List<String> requiredFacts = readJsonArray(item.getRequiredFacts());
        List<String> forbiddenFacts = readJsonArray(item.getForbiddenFacts());
        String expectedAsset = normalize(item.getExpectedAsset());
        if (expectedChunkIds.isEmpty() && expectedAsset.isBlank() && requiredFacts.isEmpty()) {
            throw invalid("运行前请标注目标资料、目标片段 ID 或必需事实。");
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", item.getProjectId());
        payload.put("query", item.getQuery());
        payload.put("topK", RETRIEVAL_TOP_K);
        payload.put("retrievalMode", "HYBRID");
        payload.put("useReranker", false);
        Map<String, Object> runtime = runtimeConfigResolver.resolveEmbeddingPayload(
                workspaceId, item.getProjectId(), userId, null
        );
        if (runtime.get("embedding") != null) payload.put("runtimeEmbedding", runtime.get("embedding"));

        Map<String, Object> response = aiClient.knowledge("/internal/knowledge/search", payload);
        Object rawData = response.get("data");
        Map<?, ?> data = rawData instanceof Map<?, ?> map ? map : response;
        List<?> results = data.get("items") instanceof List<?> list ? list : List.of();
        List<Map<?, ?>> retrieved = new ArrayList<>();
        for (Object result : results) {
            if (result instanceof Map<?, ?> map) retrieved.add(map);
        }

        Set<String> retrievedChunkIds = new LinkedHashSet<>();
        Set<String> retrievedAssets = new LinkedHashSet<>();
        StringBuilder retrievedText = new StringBuilder();
        for (Map<?, ?> result : retrieved) {
            String chunkId = value(result, "chunkId", "chunk_id");
            if (!chunkId.isBlank()) retrievedChunkIds.add(chunkId);
            String asset = value(result, "assetName", "asset_name");
            if (asset.isBlank()) asset = value(result, "sourceName", "source_name");
            if (!asset.isBlank()) retrievedAssets.add(asset);
            retrievedText.append(' ').append(value(result, "content", "content"));
        }

        List<String> matchedChunkIds = expectedChunkIds.stream().filter(retrievedChunkIds::contains).toList();
        List<String> missingChunkIds = expectedChunkIds.stream().filter(id -> !retrievedChunkIds.contains(id)).toList();
        boolean expectedAssetFound = !expectedAsset.isBlank() && retrievedAssets.stream()
                .anyMatch(asset -> normalize(asset).equals(expectedAsset));
        List<String> matchedRequiredFacts = requiredFacts.stream()
                .filter(fact -> containsNormalized(retrievedText.toString(), fact)).toList();
        List<String> missingRequiredFacts = requiredFacts.stream()
                .filter(fact -> !matchedRequiredFacts.contains(fact)).toList();
        List<String> matchedForbiddenFacts = forbiddenFacts.stream()
                .filter(fact -> containsNormalized(retrievedText.toString(), fact)).toList();

        int targetCount = !expectedChunkIds.isEmpty() ? expectedChunkIds.size()
                : !expectedAsset.isBlank() ? 1 : requiredFacts.size();
        int matchedCount = !expectedChunkIds.isEmpty() ? matchedChunkIds.size()
                : !expectedAsset.isBlank() ? (expectedAssetFound ? 1 : 0) : matchedRequiredFacts.size();
        double recall = targetCount == 0 ? 0 : Math.round(matchedCount * 10_000.0 / targetCount) / 100.0;
        boolean passed = matchedCount == targetCount
                && (expectedAsset.isBlank() || expectedAssetFound)
                && missingRequiredFacts.isEmpty()
                && matchedForbiddenFacts.isEmpty();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("metric", "Recall@" + RETRIEVAL_TOP_K);
        result.put("topK", RETRIEVAL_TOP_K);
        result.put("retrievedCount", retrieved.size());
        result.put("retrievedChunkIds", List.copyOf(retrievedChunkIds));
        result.put("retrievedAssets", List.copyOf(retrievedAssets));
        result.put("matchedChunkIds", matchedChunkIds);
        result.put("missingChunkIds", missingChunkIds);
        result.put("expectedAssetFound", expectedAssetFound);
        result.put("matchedRequiredFacts", matchedRequiredFacts);
        result.put("missingRequiredFacts", missingRequiredFacts);
        result.put("matchedForbiddenFacts", matchedForbiddenFacts);
        result.put("expectedChunkIds", expectedChunkIds);
        result.put("expectedAsset", item.getExpectedAsset());
        result.put("targetCount", targetCount);
        result.put("matchedCount", matchedCount);
        result.put("recall", recall);
        result.put("status", passed ? "PASSED" : "FAILED");

        if (mapper.saveEvaluationResult(
                workspaceId, caseId, userId, recall, passed ? "PASSED" : "FAILED", writeJson(result)
        ) == 0) {
            throw notFound();
        }
        notificationService.create(
                workspaceId,
                userId,
                item.getProjectId(),
                "evaluation",
                passed ? "检索评估已通过" : "检索评估未通过",
                "“" + item.getQuery() + "”的 Recall@" + RETRIEVAL_TOP_K + " 为 " + recall + "%。",
                "project-evaluation"
        );
        return Result.success(required(workspaceId, caseId, userId));
    }

    private EvaluationCase required(Long workspaceId, Long caseId, Long userId) {
        EvaluationCase item = mapper.findById(workspaceId, caseId, userId);
        if (item == null) throw notFound();
        return item;
    }

    private boolean containsDefinition(Map<String, Object> body) {
        return List.of("query", "expectedAnswer", "expectedAsset", "expectedChunkIds", "requiredFacts", "forbiddenFacts")
                .stream().anyMatch(body::containsKey);
    }

    private List<String> normalizeValues(Object raw) {
        if (!(raw instanceof List<?> values)) return List.of();
        List<String> normalized = values.stream().map(this::stringValue).map(String::trim)
                .filter(value -> !value.isBlank()).distinct().toList();
        if (normalized.size() > 50 || normalized.stream().anyMatch(value -> value.length() > 1000)) {
            throw invalid("每类评估标注最多 50 项，每项不能超过 1000 个字符。");
        }
        return normalized;
    }

    private List<String> readJsonArray(String json) {
        if (json == null || json.isBlank()) return List.of();
        try {
            Object parsed = objectMapper.readValue(json, List.class);
            return normalizeValues(parsed);
        } catch (RuntimeException exception) {
            return List.of();
        }
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (RuntimeException exception) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_EVALUATION_DATA", "评估标注格式不正确");
        }
    }

    private boolean containsNormalized(String haystack, String needle) {
        String target = normalize(needle);
        return !target.isBlank() && normalize(haystack).contains(target);
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT);
    }

    private String value(Map<?, ?> values, String camel, String snake) {
        Object raw = values.containsKey(camel) ? values.get(camel) : values.get(snake);
        return raw == null ? "" : String.valueOf(raw);
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String trimToNull(String value) {
        String trimmed = value == null ? "" : value.trim();
        return trimmed.isBlank() ? null : trimmed;
    }

    private String normalizeExpectedAsset(String value) {
        String asset = trimToNull(value);
        if (asset != null && asset.length() > 500) {
            throw invalid("目标资料名不能超过 500 个字符。");
        }
        return asset;
    }

    private ApiException invalid(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "INVALID_EVALUATION_CASE", message);
    }

    private String normalizeStatus(Object value) {
        if (value == null) {
            throw new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "INVALID_EVALUATION_STATUS",
                    "评估状态不能为空"
            );
        }
        return switch (String.valueOf(value).trim().toUpperCase(Locale.ROOT)) {
            case "PASSED" -> "PASSED";
            case "REVIEW" -> "REVIEW";
            case "FAILED" -> "FAILED";
            default -> throw new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "INVALID_EVALUATION_STATUS",
                    "评估状态不正确"
            );
        };
    }

    private ApiException notFound() {
        return new ApiException(
                HttpStatus.NOT_FOUND,
                "EVALUATION_CASE_NOT_FOUND",
                "评估用例不存在或无权访问"
        );
    }

    private Long userId(Authentication auth) {
        return ((UserLoginByPassword) auth.getPrincipal()).getId();
    }

    public record CaseRequest(
            Long projectId,
            @NotBlank String query,
            String expectedAnswer,
            String expectedAsset,
            List<String> expectedChunkIds,
            List<String> requiredFacts,
            List<String> forbiddenFacts
    ) {
    }
}
