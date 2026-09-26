package com.cuupe.backend.modules.settings.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.config.security.SecretCipher;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.settings.dto.ModelConfigRequest;
import com.cuupe.backend.modules.settings.entity.ModelConfig;
import com.cuupe.backend.modules.settings.mapper.ModelConfigMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/settings/models")
@RequiredArgsConstructor
public class WorkspaceModelSettingsController {
    private final WorkspaceMapper workspaceMapper;
    private final ModelConfigMapper modelMapper;
    private final SecretCipher cipher;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final AiIndexingClient aiClient;
    private final ObjectMapper objectMapper;
    private final AuditLogService auditLogService;

    /** Returns only the current user's models and models explicitly marked as the workspace default. */
    @GetMapping
    public Result<List<ModelConfig>> list(@PathVariable Long workspaceId, Authentication auth) {
        Long userId = userId(auth);
        requiredWorkspace(workspaceId, userId);
        return Result.success(modelMapper.findForManagement(workspaceId, userId));
    }

    @PostMapping
    public Result<ModelConfig> create(@PathVariable Long workspaceId,
                                      @Valid @RequestBody ModelConfigRequest request,
                                      Authentication auth) {
        Long userId = userId(auth);
        requiredWorkspace(workspaceId, userId);
        ModelConfig config = new ModelConfig();
        config.setWorkspaceId(workspaceId);
        config.setCreatedBy(userId);
        config.setName(request.name().trim());
        config.setProvider(request.provider().trim());
        config.setModelId(request.modelId().trim());
        config.setEndpoint(request.endpoint().trim());
        config.setAuthType(defaultValue(request.authType(), "API_KEY"));
        config.setCredentialCiphertext(resolveCredential(workspaceId, userId, request));
        config.setConfig(validateModelConfig(defaultValue(request.config(), "{}")));
        config.setEnabled(request.enabled() == null || request.enabled());
        config.setDefaultModel(false);
        modelMapper.insert(config);
        auditLogService.record(workspaceId, null, userId, "MODEL_CONFIG_CREATED", "MODEL_CONFIG", config.getId(),
                Map.of("provider", config.getProvider(), "scope", "WORKSPACE_PERSONAL"));
        return Result.success(modelMapper.findVisibleById(config.getId(), workspaceId, userId));
    }

    @PatchMapping("/{id}")
    public Result<ModelConfig> update(@PathVariable Long workspaceId,
                                      @PathVariable Long id,
                                      @Valid @RequestBody ModelConfigRequest request,
                                      Authentication auth) {
        Long userId = userId(auth);
        ModelConfig current = requiredOwnedModel(workspaceId, id, userId);
        current.setName(request.name().trim());
        current.setProvider(request.provider().trim());
        current.setModelId(request.modelId().trim());
        current.setEndpoint(request.endpoint().trim());
        current.setAuthType(defaultValue(request.authType(), current.getAuthType()));
        if (request.credential() != null && !request.credential().isBlank()) {
            current.setCredentialCiphertext(cipher.encrypt(request.credential().trim()));
        }
        current.setConfig(validateModelConfig(defaultValue(request.config(), current.getConfig())));
        if (request.enabled() != null) current.setEnabled(request.enabled());
        current.setWorkspaceId(workspaceId);
        current.setCreatedBy(userId);
        if (modelMapper.update(current) == 0) throw notFound();
        auditLogService.record(workspaceId, null, userId, "MODEL_CONFIG_UPDATED", "MODEL_CONFIG", id);
        return Result.success(modelMapper.findVisibleById(id, workspaceId, userId));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long workspaceId, @PathVariable Long id, Authentication auth) {
        Long userId = userId(auth);
        ModelConfig current = requiredOwnedModel(workspaceId, id, userId);
        if (modelMapper.delete(current.getId(), workspaceId, userId) == 0) throw notFound();
        auditLogService.record(workspaceId, null, userId, "MODEL_CONFIG_DELETED", "MODEL_CONFIG", id);
        return Result.success();
    }

    @PutMapping("/default")
    @Transactional
    public Result<List<ModelConfig>> setDefault(@PathVariable Long workspaceId,
                                                @RequestBody DefaultModelRequest request,
                                                Authentication auth) {
        Long userId = userId(auth);
        requiredWorkspace(workspaceId, userId);
        ModelConfig selected = null;
        if (request != null && request.modelId() != null) {
            selected = requiredOwnedModel(workspaceId, request.modelId(), userId);
            if (!selected.isEnabled() || isEmbedding(selected)) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_DEFAULT_MODEL", "默认模型必须是已启用的文本模型");
            }
        }
        modelMapper.clearDefault(workspaceId);
        if (selected != null && modelMapper.setDefault(selected.getId(), workspaceId, userId) == 0) throw notFound();
        auditLogService.record(workspaceId, null, userId, "MODEL_DEFAULT_UPDATED", "WORKSPACE", workspaceId);
        return Result.success(modelMapper.findForManagement(workspaceId, userId));
    }

    @PostMapping("/{id}/test")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> test(@PathVariable Long workspaceId, @PathVariable Long id, Authentication auth) {
        Long userId = userId(auth);
        requiredVisibleModel(workspaceId, id, userId);
        try {
            Map<String, Object> payload = runtimeConfigResolver.resolveWorkspaceModelPayload(workspaceId, userId, id);
            if (payload.isEmpty()) throw new ApiException(HttpStatus.BAD_REQUEST, "MODEL_CONFIG_UNAVAILABLE", "模型配置不可用");
            return Result.success(aiClient.testModel((Map<String, Object>) payload.get("model")));
        } catch (ApiException exception) {
            throw exception;
        } catch (IllegalStateException exception) {
            throw credentialFailure(exception, "模型");
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "MODEL_CONNECTION_FAILED", explainModelConnectionFailure(exception));
        }
    }

    @PostMapping("/{id}/context")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> context(@PathVariable Long workspaceId, @PathVariable Long id, Authentication auth) {
        Long userId = userId(auth);
        requiredVisibleModel(workspaceId, id, userId);
        try {
            Map<String, Object> payload = runtimeConfigResolver.resolveWorkspaceModelPayload(workspaceId, userId, id);
            if (payload.isEmpty()) throw new ApiException(HttpStatus.BAD_REQUEST, "MODEL_CONFIG_UNAVAILABLE", "模型配置不可用");
            return Result.success(aiClient.modelContext((Map<String, Object>) payload.get("model")));
        } catch (ApiException exception) {
            throw exception;
        } catch (IllegalStateException exception) {
            throw credentialFailure(exception, "模型");
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "MODEL_CONTEXT_LOOKUP_FAILED", "模型上下文窗口获取失败");
        }
    }

    @PostMapping("/{id}/test-embedding")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testEmbedding(@PathVariable Long workspaceId, @PathVariable Long id, Authentication auth) {
        Long userId = userId(auth);
        requiredVisibleModel(workspaceId, id, userId);
        try {
            Map<String, Object> payload = runtimeConfigResolver.resolveWorkspaceEmbeddingPayload(workspaceId, userId, id);
            if (payload.isEmpty()) throw new ApiException(HttpStatus.BAD_REQUEST, "EMBEDDING_CONFIG_UNAVAILABLE", "Embedding 配置不可用");
            return Result.success(aiClient.testEmbedding((Map<String, Object>) payload.get("embedding")));
        } catch (ApiException exception) {
            throw exception;
        } catch (IllegalStateException exception) {
            throw credentialFailure(exception, "Embedding");
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "EMBEDDING_CONNECTION_FAILED", "Embedding 连接测试失败");
        }
    }

    private Workspace requiredWorkspace(Long workspaceId, Long userId) {
        Workspace workspace = workspaceMapper.findAccessible(workspaceId, userId);
        if (workspace == null) throw new ApiException(HttpStatus.NOT_FOUND, "WORKSPACE_NOT_FOUND", "工作区不存在或无权访问");
        return workspace;
    }

    private ModelConfig requiredOwnedModel(Long workspaceId, Long id, Long userId) {
        requiredWorkspace(workspaceId, userId);
        ModelConfig config = modelMapper.findOwnedById(id, workspaceId, userId);
        if (config == null) throw notFound();
        return config;
    }

    private ModelConfig requiredVisibleModel(Long workspaceId, Long id, Long userId) {
        requiredWorkspace(workspaceId, userId);
        ModelConfig config = modelMapper.findVisibleById(id, workspaceId, userId);
        if (config == null) throw notFound();
        return config;
    }

    private ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "MODEL_CONFIG_NOT_FOUND", "模型配置不存在或无权访问");
    }

    private String resolveCredential(Long workspaceId, Long userId, ModelConfigRequest request) {
        if (request.credential() != null && !request.credential().isBlank()) return cipher.encrypt(request.credential().trim());
        if (request.credentialSourceId() == null) return null;
        ModelConfig source = modelMapper.findVisibleById(request.credentialSourceId(), workspaceId, userId);
        String requestedAuthType = defaultValue(request.authType(), "API_KEY");
        if (source == null || !source.getProvider().trim().equalsIgnoreCase(request.provider().trim())
                || !source.getEndpoint().trim().equals(request.endpoint().trim())
                || !source.getAuthType().trim().equalsIgnoreCase(requestedAuthType.trim())
                || source.getCredentialCiphertext() == null || source.getCredentialCiphertext().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "MODEL_CREDENTIAL_SOURCE_UNAVAILABLE", "选择的服务连接没有可复用的有效凭证");
        }
        return source.getCredentialCiphertext();
    }

    private String defaultValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    @SuppressWarnings("unchecked")
    private String validateModelConfig(String value) {
        try {
            Map<String, Object> config = objectMapper.readValue(value == null || value.isBlank() ? "{}" : value, Map.class);
            validateRange(config, "temperature", 0, 2);
            validateRange(config, "topP", 0.000001, 1);
            validateRange(config, "topK", 1, 1000);
            validateRange(config, "maxTokens", 1, 1_000_000);
            validateRange(config, "contextWindow", 1, 1_000_000);
            validateRange(config, "frequencyPenalty", -2, 2);
            validateRange(config, "presencePenalty", -2, 2);
            validateRange(config, "seed", 0, Integer.MAX_VALUE);
            validateRange(config, "timeout", 1, 600);
            validateRange(config, "retries", 0, 5);
            Object stop = config.get("stop");
            if (stop != null && (!(stop instanceof List<?> values) || values.size() > 4)) throw invalidModelConfig();
            Object extraBody = config.get("extraBody");
            if (extraBody != null && !(extraBody instanceof Map<?, ?>)) throw invalidModelConfig();
            String reasoning = String.valueOf(config.getOrDefault("reasoningEffort", "high"));
            if (!List.of("none", "low", "medium", "high").contains(reasoning)) throw invalidModelConfig();
            String structured = String.valueOf(config.getOrDefault("structuredOutputMethod", "json_schema"));
            if (!List.of("json_schema", "function_calling", "json_mode").contains(structured)) throw invalidModelConfig();
            return value;
        } catch (ApiException exception) {
            throw exception;
        } catch (Exception exception) {
            throw invalidModelConfig();
        }
    }

    private void validateRange(Map<String, Object> config, String key, double min, double max) {
        Object value = config.get(key);
        if (value == null) return;
        double number;
        try { number = value instanceof Number item ? item.doubleValue() : Double.parseDouble(String.valueOf(value)); }
        catch (Exception exception) { throw invalidModelConfig(); }
        if (!Double.isFinite(number) || number < min || number > max) throw invalidModelConfig();
    }

    private ApiException invalidModelConfig() {
        return new ApiException(HttpStatus.BAD_REQUEST, "INVALID_MODEL_CONFIG", "模型高级参数不符合允许范围");
    }

    private ApiException credentialFailure(IllegalStateException exception, String resourceName) {
        String message = exception.getMessage() == null ? "" : exception.getMessage();
        if (message.contains("凭证") || message.contains("credential")) {
            return new ApiException(HttpStatus.BAD_REQUEST, "MODEL_CREDENTIAL_MISSING", resourceName + "配置缺少有效访问凭证");
        }
        return new ApiException(HttpStatus.BAD_GATEWAY, "MODEL_CONNECTION_FAILED", explainModelConnectionFailure(exception));
    }

    private String explainModelConnectionFailure(Exception exception) {
        String detail = exception.getMessage() == null ? "" : exception.getMessage();
        String normalized = detail.toLowerCase();
        if (normalized.contains("401") || normalized.contains("unauthorized") || normalized.contains("invalid api key")) {
            return "模型连接失败：API Key 无效，请重新填写有效凭证";
        }
        if (normalized.contains("404") || normalized.contains("not found")) {
            return "模型连接失败：服务地址或模型 ID 不存在，请检查 OpenAI 兼容地址和模型 ID";
        }
        if (normalized.contains("timeout") || normalized.contains("timed out")) {
            return "模型连接失败：请求超时，请检查网络或提高超时配置";
        }
        return detail.isBlank() ? "模型连接失败：未收到上游诊断信息" : "模型连接失败：" + detail;
    }

    private boolean isEmbedding(ModelConfig model) {
        if (model.getConfig() == null || model.getConfig().isBlank()) return false;
        try {
            Map<String, Object> config = objectMapper.readValue(model.getConfig(), Map.class);
            return "EMBEDDING".equalsIgnoreCase(String.valueOf(config.getOrDefault("use", "")));
        } catch (Exception ignored) {
            return false;
        }
    }

    private Long userId(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("Current session does not contain user information");
    }

    public record DefaultModelRequest(Long modelId) { }
}
