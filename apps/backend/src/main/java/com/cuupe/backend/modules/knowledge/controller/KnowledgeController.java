package com.cuupe.backend.modules.knowledge.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.agent.mapper.AgentMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {
    private final AgentMapper accessMapper;
    private final AiIndexingClient aiClient;
    private final RuntimeConfigResolver runtimeConfigResolver;

    @PostMapping("/search")
    public Result<Map<String, Object>> search(@PathVariable Long workspaceId, @PathVariable Long projectId, @RequestBody Map<String, Object> body, Authentication authentication) throws IOException {
        Long userId = userId(authentication);
        if (!accessMapper.hasProjectAccess(workspaceId, projectId, userId)) throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        Map<String, Object> payload = new LinkedHashMap<>(body);
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", projectId);
        Map<String, Object> runtime = runtimeConfigResolver.resolveEmbeddingPayload(projectId, userId, body.get("embeddingConfigId"));
        if (runtime.get("embedding") != null) payload.put("runtimeEmbedding", runtime.get("embedding"));
        Map<String, Object> response = aiClient.knowledge("/internal/knowledge/search", payload);
        Object data = response.get("data");
        return Result.success(data instanceof Map ? (Map<String, Object>) data : response);
    }

    @PostMapping("/answer")
    public Result<Map<String, Object>> answer(@PathVariable Long workspaceId, @PathVariable Long projectId, @RequestBody Map<String, Object> body, Authentication authentication) throws IOException {
        Long userId = userId(authentication);
        if (!accessMapper.hasProjectAccess(workspaceId, projectId, userId)) throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        Map<String, Object> payload = new LinkedHashMap<>(body);
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", projectId);
        Map<String, Object> runtime = runtimeConfigResolver.resolve(projectId, userId, body);
        if (runtime.get("model") != null) payload.put("runtimeModel", runtime.get("model"));
        if (runtime.get("embedding") != null) payload.put("runtimeEmbedding", runtime.get("embedding"));
        Map<String, Object> response = aiClient.knowledge("/internal/knowledge/answer", payload);
        Object data = response.get("data");
        return Result.success(data instanceof Map ? (Map<String, Object>) data : response);
    }

    private Long userId(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }
}
