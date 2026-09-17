package com.cuupe.backend.modules.research.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.research.entity.ResearchRun;
import com.cuupe.backend.modules.research.mapper.ResearchRunMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.entity.ProjectReviewPolicy;
import com.cuupe.backend.modules.project.mapper.ProjectReviewMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.ObjectMapper;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/runs")
@RequiredArgsConstructor
public class ResearchRunController {
    private final ResearchRunMapper mapper;
    private final ObjectMapper objectMapper;
    private final NotificationService notificationService;
    private final AiIndexingClient aiClient;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final AuditLogService auditLogService;
    private final WorkspaceMapper workspaceMapper;
    private final ProjectMapper projectMapper;
    private final ProjectReviewMapper projectReviewMapper;

    @GetMapping
    public Result<List<ResearchRun>> list(@PathVariable Long projectId, Authentication auth) {
        return Result.success(mapper.findByProject(projectId, userId(auth)));
    }

    @PostMapping
    public Result<ResearchRun> create(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @RequestBody Map<String, Object> body,
            Authentication auth
    ) {
        String goal = String.valueOf(body.getOrDefault("goal", "")).trim();
        if (goal.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "调研目标不能为空");
        }
        ResearchRun run = new ResearchRun();
        Long userId = userId(auth);
        run.setProjectId(projectId);
        run.setCreatedBy(userId);
        run.setGoal(goal);
        run.setTitle(goal.length() > 80 ? goal.substring(0, 80) : goal);
        run.setPriority(String.valueOf(body.getOrDefault("priority", "NORMAL")).toUpperCase(Locale.ROOT));
        run.setConfig(toConfig(body));
        mapper.insert(run);
        auditLogService.record(workspaceId, projectId, userId, "RESEARCH_RUN_CREATED", "RESEARCH_RUN", run.getId(), Map.of("title", run.getTitle()));
        notificationService.create(
                workspaceId,
                userId(auth),
                projectId,
                "research",
                "调研运行已创建",
                "“" + run.getTitle() + "”调研任务已进入队列。",
                "project-runs"
        );
        dispatch(run, workspaceId, userId(auth), body);
        return Result.success(mapper.findById(run.getId(), projectId, userId(auth)));
    }

    @GetMapping("/{runId}")
    public Result<Map<String, Object>> detail(@PathVariable Long projectId, @PathVariable Long runId, Authentication auth) {
        ResearchRun run = required(runId, projectId, userId(auth));
        Map<String, Object> detail = new LinkedHashMap<>(objectMapper.convertValue(run, Map.class));
        try {
            detail.putAll(aiClient.runDetail(String.valueOf(runId)));
        } catch (Exception ignored) {
            // The Java record remains available while the AI service is restarting.
        }
        return Result.success(detail);
    }

    @PostMapping("/{runId}/cancel")
    public Result<ResearchRun> cancel(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long runId, Authentication auth) {
        Long userId = userId(auth);
        Result<ResearchRun> result = change(runId, projectId, userId, "CANCELLED");
        auditLogService.record(workspaceId, projectId, userId, "RESEARCH_RUN_CANCELLED", "RESEARCH_RUN", runId);
        Thread.startVirtualThread(() -> { try { aiClient.cancelRun(runId); } catch (Exception ignored) { } });
        return result;
    }

    @PostMapping("/{runId}/retry")
    public Result<ResearchRun> retry(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long runId, Authentication auth) {
        Long userId = userId(auth);
        Result<ResearchRun> result = change(runId, projectId, userId, "PENDING");
        auditLogService.record(workspaceId, projectId, userId, "RESEARCH_RUN_RETRIED", "RESEARCH_RUN", runId);
        ResearchRun run = required(runId, projectId, userId);
        dispatch(run, workspaceId, userId, readConfig(run.getConfig()));
        return result;
    }

    @PatchMapping("/{runId}/plan")
    public Result<Map<String, Object>> updatePlan(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @PathVariable Long runId,
            @RequestBody Map<String, Object> body,
            Authentication auth
    ) {
        Long userId = userId(auth);
        requiredWriteProject(workspaceId, projectId, userId);
        required(runId, projectId, userId);
        try {
            Map<String, Object> response = aiClient.updatePlan(String.valueOf(runId), body);
            auditLogService.record(workspaceId, projectId, userId, "RESEARCH_PLAN_UPDATED", "RESEARCH_RUN", runId,
                    Map.of("mode", String.valueOf(body.getOrDefault("mode", "APPEND"))));
            return Result.success(response);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "RESEARCH_PLAN_UPDATE_FAILED", "AI 计划更新失败：" + exception.getMessage());
        }
    }

    private String toConfig(Map<String, Object> body) {
        Map<String, Object> config = new LinkedHashMap<>();
        for (String key : List.of("allowWebSearch", "maxResearchRounds", "reportTemplate", "outputLanguage", "topK", "retrievalMode", "useReranker", "modelConfigId")) {
            if (body.containsKey(key)) config.put(key, body.get(key));
        }
        try {
            return objectMapper.writeValueAsString(config);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_RUN_CONFIG", "调研配置格式不正确");
        }
    }

    private Result<ResearchRun> change(Long id, Long projectId, Long userId, String status) {
        required(id, projectId, userId);
        if (mapper.updateStatus(id, projectId, userId, status) == 0) throw notFound();
        return Result.success(mapper.findById(id, projectId, userId));
    }

    private void dispatch(ResearchRun run, Long workspaceId, Long userId, Map<String, Object> requestConfig) {
        Long resolvedWorkspaceId = workspaceId;
        Thread.startVirtualThread(() -> {
            try {
                Map<String, Object> runtime = runtimeConfigResolver.resolve(resolvedWorkspaceId, run.getProjectId(), userId, requestConfig);
                Map<String, Object> config = readConfig(run.getConfig());
                config.putAll(agentPolicy(resolvedWorkspaceId, run.getProjectId(), userId));
                aiClient.executeRun(run.getId(), resolvedWorkspaceId, run.getProjectId(), userId, run.getGoal(), objectMapper.writeValueAsString(config), runtime);
            } catch (Exception exception) {
                mapper.updateStatus(run.getId(), run.getProjectId(), userId, "FAILED");
            }
        });
    }

    private void requiredWriteProject(Long workspaceId, Long projectId, Long userId) {
        if (projectMapper.findAccessibleById(workspaceId, projectId, userId) == null) throw notFound();
        if (!projectMapper.hasWriteAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "RESEARCH_PLAN_FORBIDDEN", "只有项目创建者或管理员可以修改执行计划");
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> agentPolicy(Long workspaceId, Long projectId, Long userId) {
        Map<String, Object> result = new LinkedHashMap<>();
        ProjectReviewPolicy reviewPolicy = projectReviewMapper.findPolicy(workspaceId, projectId);
        if (reviewPolicy != null) {
            result.put("reviewPolicy", Map.of(
                    "requireCitations", reviewPolicy.isRequireCitations(),
                    "verifyNumbers", reviewPolicy.isVerifyNumbers(),
                    "escalateConflicts", reviewPolicy.isEscalateConflicts(),
                    "labelExternal", reviewPolicy.isLabelExternal()));
        }
        Workspace workspace = workspaceMapper.findAccessible(workspaceId, userId);
        if (workspace == null || workspace.getPreferences() == null || workspace.getPreferences().isBlank()) return result;
        try {
            Map<String, Object> preferences = objectMapper.readValue(workspace.getPreferences(), Map.class);
            Object raw = preferences.get("agentPolicy");
            if (raw instanceof Map<?, ?> policy) {
                if (policy.get("maxCalls") != null) result.put("toolMaxCalls", policy.get("maxCalls"));
                if (policy.get("requireApproval") != null) result.put("requireToolApproval", policy.get("requireApproval"));
            }
            Object localTools = preferences.get("localTools");
            if (localTools instanceof Map<?, ?> configuredTools) {
                List<String> disabledTools = new java.util.ArrayList<>();
                for (Map.Entry<?, ?> entry : configuredTools.entrySet()) {
                    if (Boolean.FALSE.equals(entry.getValue())) disabledTools.add(String.valueOf(entry.getKey()));
                }
                if (!disabledTools.isEmpty()) result.put("disabledTools", disabledTools);
            }
            return result;
        } catch (Exception ignored) { return result; }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> readConfig(String value) {
        try { return objectMapper.readValue(value == null ? "{}" : value, Map.class); }
        catch (Exception ignored) { return Map.of(); }
    }

    private ResearchRun required(Long id, Long projectId, Long userId) {
        ResearchRun run = mapper.findById(id, projectId, userId);
        if (run == null) throw notFound();
        return run;
    }

    private Long userId(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }

    private ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "RESEARCH_RUN_NOT_FOUND", "运行不存在或无权访问");
    }
}
