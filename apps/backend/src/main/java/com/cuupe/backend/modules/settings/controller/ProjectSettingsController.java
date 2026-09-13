package com.cuupe.backend.modules.settings.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.config.security.SecretCipher;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.settings.dto.ModelConfigRequest;
import com.cuupe.backend.modules.settings.dto.ToolConfigRequest;
import com.cuupe.backend.modules.settings.entity.ModelConfig;
import com.cuupe.backend.modules.settings.entity.ToolConfig;
import com.cuupe.backend.modules.settings.mapper.ModelConfigMapper;
import com.cuupe.backend.modules.settings.mapper.ToolConfigMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/settings")
@RequiredArgsConstructor
public class ProjectSettingsController {
    private final ProjectMapper projectMapper;
    private final ModelConfigMapper modelMapper;
    private final ToolConfigMapper toolMapper;
    private final SecretCipher cipher;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final AiIndexingClient aiClient;
    private final ObjectMapper objectMapper;
    private final AuditLogService auditLogService;

    @GetMapping("/models")
    public Result<List<ModelConfig>> models(@PathVariable Long projectId, Authentication auth) {
        return Result.success(modelMapper.findByProject(projectId, userId(auth)));
    }

    @PostMapping("/models")
    public Result<ModelConfig> createModel(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                           @Valid @RequestBody ModelConfigRequest request, Authentication auth) {
        Long currentUserId = userId(auth);
        String scope = "PERSONAL";
        accessForCreate(workspaceId, projectId, currentUserId, scope);
        ModelConfig config = new ModelConfig();
        config.setProjectId(projectId);
        config.setCreatedBy(currentUserId);
        config.setName(request.name().trim());
        config.setProvider(request.provider().trim());
        config.setModelId(request.modelId().trim());
        config.setEndpoint(request.endpoint().trim());
        config.setAuthType(defaultValue(request.authType(), "API_KEY"));
        config.setCredentialCiphertext(resolveCredential(projectId, currentUserId, request));
        config.setConfig(validateModelConfig(defaultValue(request.config(), "{}")));
        config.setEnabled(request.enabled() == null || request.enabled());
        config.setScope(scope);
        modelMapper.insert(config);
        auditLogService.record(workspaceId, projectId, currentUserId, "MODEL_CONFIG_CREATED", "MODEL_CONFIG", config.getId(), Map.of("provider", config.getProvider(), "scope", config.getScope()));
        return Result.success(modelMapper.findById(config.getId(), projectId, currentUserId));
    }

    @PatchMapping("/models/{id}")
    public Result<ModelConfig> updateModel(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                           @PathVariable Long id, @Valid @RequestBody ModelConfigRequest request,
                                           Authentication auth) {
        Long currentUserId = userId(auth);
        ModelConfig config = requiredModel(id, projectId, currentUserId);
        String scope = "PERSONAL";
        modelAccessForUpdate(workspaceId, projectId, currentUserId, config);
        config.setName(request.name().trim());
        config.setProvider(request.provider().trim());
        config.setModelId(request.modelId().trim());
        config.setEndpoint(request.endpoint().trim());
        config.setAuthType(defaultValue(request.authType(), config.getAuthType()));
        if (request.credential() != null && !request.credential().isBlank()) {
            config.setCredentialCiphertext(cipher.encrypt(request.credential()));
        }
        config.setConfig(validateModelConfig(defaultValue(request.config(), config.getConfig())));
        if (request.enabled() != null) config.setEnabled(request.enabled());
        config.setScope(scope);
        modelMapper.update(config);
        auditLogService.record(workspaceId, projectId, currentUserId, "MODEL_CONFIG_UPDATED", "MODEL_CONFIG", config.getId(), Map.of("provider", config.getProvider(), "scope", config.getScope()));
        return Result.success(modelMapper.findById(id, projectId, currentUserId));
    }

    @DeleteMapping("/models/{id}")
    public Result<Void> deleteModel(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                    @PathVariable Long id, Authentication auth) {
        Long currentUserId = userId(auth);
        ModelConfig config = requiredModel(id, projectId, currentUserId);
        modelAccessForUpdate(workspaceId, projectId, currentUserId, config);
        modelMapper.delete(id, projectId);
        auditLogService.record(workspaceId, projectId, currentUserId, "MODEL_CONFIG_DELETED", "MODEL_CONFIG", id);
        return Result.success();
    }

    @PostMapping("/models/{id}/test")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testModel(@PathVariable Long projectId, @PathVariable Long id,
                                                  Authentication auth) {
        try {
            Map<String, Object> payload = runtimeConfigResolver.resolveModelPayload(projectId, userId(auth), id);
            if (payload.isEmpty()) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "MODEL_CONFIG_UNAVAILABLE", "模型配置不可用");
            }
            return Result.success(aiClient.testModel((Map<String, Object>) payload.get("model")));
        } catch (ApiException exception) {
            throw exception;
        } catch (IllegalStateException exception) {
            throw credentialFailure(exception, "模型");
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "MODEL_CONNECTION_FAILED", explainModelConnectionFailure(exception));
        }
    }

    @PostMapping("/models/{id}/test-embedding")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> testEmbedding(@PathVariable Long projectId, @PathVariable Long id,
                                                      Authentication auth) {
        try {
            Map<String, Object> payload = runtimeConfigResolver.resolveEmbeddingPayload(projectId, userId(auth), id);
            if (payload.isEmpty()) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "EMBEDDING_CONFIG_UNAVAILABLE", "Embedding 配置不可用");
            }
            return Result.success(aiClient.testEmbedding((Map<String, Object>) payload.get("embedding")));
        } catch (ApiException exception) {
            throw exception;
        } catch (IllegalStateException exception) {
            throw credentialFailure(exception, "Embedding");
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "EMBEDDING_CONNECTION_FAILED", "Embedding 连接测试失败");
        }
    }

    private ApiException credentialFailure(IllegalStateException exception, String resourceName) {
        if (containsCredentialDecryptionFailure(exception)) {
            return new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "MODEL_CREDENTIAL_DECRYPT_FAILED",
                    "无法读取" + resourceName + "访问凭证：后端加密密钥与保存凭证时不一致，或凭证已损坏。请确认 SHINKOU_ENCRYPTION_KEY 未变化；如果无法恢复原密钥，请在编辑配置中重新输入真实 API Key 并保存后再测试。"
            );
        }
        if (containsMessage(exception, "缺少凭证")) {
            return new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "MODEL_CREDENTIAL_MISSING",
                    resourceName + "配置没有保存访问凭证，请编辑配置后重新输入 API Key 并保存。"
            );
        }
        return new ApiException(HttpStatus.BAD_GATEWAY, "MODEL_CONNECTION_FAILED", explainModelConnectionFailure(exception));
    }

    private boolean containsCredentialDecryptionFailure(Throwable exception) {
        Throwable current = exception;
        while (current != null) {
            if (current instanceof java.security.GeneralSecurityException
                    && "AEADBadTagException".equals(current.getClass().getSimpleName())) {
                return true;
            }
            if (containsMessage(current, "无法解密配置凭证")) return true;
            current = current.getCause();
        }
        return false;
    }

    private boolean containsMessage(Throwable exception, String text) {
        return exception != null && exception.getMessage() != null && exception.getMessage().contains(text);
    }

    @GetMapping("/tools")
    public Result<List<ToolConfig>> tools(@PathVariable Long projectId, Authentication auth) {
        return Result.success(toolMapper.findByProject(projectId, userId(auth)));
    }

    @PostMapping("/tools")
    public Result<ToolConfig> createTool(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                         @Valid @RequestBody ToolConfigRequest request, Authentication auth) {
        Long currentUserId = userId(auth);
        rejectWebSearch(request);
        String scope = scope(request.scope());
        accessForCreate(workspaceId, projectId, currentUserId, scope);
        ToolConfig config = new ToolConfig();
        config.setProjectId(projectId);
        config.setCreatedBy(currentUserId);
        config.setName(request.name().trim());
        config.setEndpoint(request.endpoint().trim());
        config.setConnectorType(defaultValue(request.connectorType(), "REST_API"));
        config.setAuthType(defaultValue(request.authType(), "API_KEY"));
        config.setCredentialCiphertext(encrypt(request.credential()));
        config.setConfig(defaultValue(request.config(), "{}"));
        config.setEnabled(request.enabled() == null || request.enabled());
        config.setScope(scope);
        toolMapper.insert(config);
        auditLogService.record(workspaceId, projectId, currentUserId, "TOOL_CONFIG_CREATED", "TOOL_CONFIG", config.getId(), Map.of("connectorType", config.getConnectorType(), "scope", config.getScope()));
        return Result.success(toolMapper.findById(config.getId(), projectId, currentUserId));
    }

    @PatchMapping("/tools/{id}")
    public Result<ToolConfig> updateTool(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                         @PathVariable Long id, @Valid @RequestBody ToolConfigRequest request,
                                         Authentication auth) {
        Long currentUserId = userId(auth);
        rejectWebSearch(request);
        ToolConfig config = requiredTool(id, projectId, currentUserId);
        String scope = scope(defaultValue(request.scope(), config.getScope()));
        accessForUpdate(workspaceId, projectId, currentUserId, config, scope);
        config.setName(request.name().trim());
        config.setEndpoint(request.endpoint().trim());
        config.setConnectorType(defaultValue(request.connectorType(), config.getConnectorType()));
        config.setAuthType(defaultValue(request.authType(), config.getAuthType()));
        if (request.credential() != null && !request.credential().isBlank()) {
            config.setCredentialCiphertext(cipher.encrypt(request.credential()));
        }
        config.setConfig(defaultValue(request.config(), config.getConfig()));
        if (request.enabled() != null) config.setEnabled(request.enabled());
        config.setScope(scope);
        toolMapper.update(config);
        auditLogService.record(workspaceId, projectId, currentUserId, "TOOL_CONFIG_UPDATED", "TOOL_CONFIG", config.getId(), Map.of("connectorType", config.getConnectorType(), "scope", config.getScope()));
        return Result.success(toolMapper.findById(id, projectId, currentUserId));
    }

    @DeleteMapping("/tools/{id}")
    public Result<Void> deleteTool(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                   @PathVariable Long id, Authentication auth) {
        Long currentUserId = userId(auth);
        ToolConfig config = requiredTool(id, projectId, currentUserId);
        accessForUpdate(workspaceId, projectId, currentUserId, config, config.getScope());
        toolMapper.delete(id, projectId);
        auditLogService.record(workspaceId, projectId, currentUserId, "TOOL_CONFIG_DELETED", "TOOL_CONFIG", id);
        return Result.success();
    }

    private Long userId(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("Current session does not contain user information");
    }

    private void accessForCreate(Long workspaceId, Long projectId, Long userId, String scope) {
        if ("PERSONAL".equals(scope)) memberAccess(workspaceId, projectId, userId);
        else writeAccess(workspaceId, projectId, userId);
    }

    private void modelAccessForUpdate(Long workspaceId, Long projectId, Long userId, ModelConfig config) {
        if (!userId.equals(config.getCreatedBy())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "MODEL_CONFIG_FORBIDDEN", "只能管理当前用户创建的模型配置");
        }
        memberAccess(workspaceId, projectId, userId);
    }

    private void accessForUpdate(Long workspaceId, Long projectId, Long userId, ToolConfig config, String scope) {
        if ("PERSONAL".equals(config.getScope()) && userId.equals(config.getCreatedBy()) && "PERSONAL".equals(scope)) {
            memberAccess(workspaceId, projectId, userId);
        } else {
            writeAccess(workspaceId, projectId, userId);
        }
    }

    private void memberAccess(Long workspaceId, Long projectId, Long userId) {
        if (projectMapper.findAccessibleById(workspaceId, projectId, userId) == null) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_SETTINGS_FORBIDDEN", "Current user cannot access this project");
        }
    }

    private void writeAccess(Long workspaceId, Long projectId, Long userId) {
        if (!projectMapper.hasWriteAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_SETTINGS_FORBIDDEN", "Only the project creator or administrator can manage shared settings");
        }
    }

    private ModelConfig requiredModel(Long id, Long projectId, Long userId) {
        ModelConfig config = modelMapper.findById(id, projectId, userId);
        if (config == null) throw new ApiException(HttpStatus.NOT_FOUND, "MODEL_CONFIG_NOT_FOUND", "Model configuration not found or inaccessible");
        return config;
    }

    private ToolConfig requiredTool(Long id, Long projectId, Long userId) {
        ToolConfig config = toolMapper.findById(id, projectId, userId);
        if (config == null) throw new ApiException(HttpStatus.NOT_FOUND, "TOOL_CONFIG_NOT_FOUND", "Tool configuration not found or inaccessible");
        return config;
    }

    private String encrypt(String value) { return value == null || value.isBlank() ? null : cipher.encrypt(value); }

    @SuppressWarnings("unchecked")
    private void rejectWebSearch(ToolConfigRequest request) {
        if ("WEB_SEARCH".equalsIgnoreCase(defaultValue(request.connectorType(), ""))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_USE_DEDICATED_SETTINGS", "联网搜索必须在独立的联网搜索设置中配置，不能作为通用连接器添加");
        }
        if (request.config() == null || request.config().isBlank()) return;
        try {
            Map<String, Object> config = objectMapper.readValue(request.config(), Map.class);
            if ("web_search".equalsIgnoreCase(String.valueOf(config.getOrDefault("purpose", "")))) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_USE_DEDICATED_SETTINGS", "联网搜索必须在独立的联网搜索设置中配置，不能作为通用连接器添加");
            }
        } catch (ApiException exception) {
            throw exception;
        } catch (Exception ignored) {
            // The normal tool validation path will report malformed tool JSON.
        }
    }

    private String explainModelConnectionFailure(Exception exception) {
        String detail = exception.getMessage() == null ? "" : exception.getMessage();
        String normalized = detail.toLowerCase();
        if (normalized.contains("401") || normalized.contains("unauthorized")
                || normalized.contains("invalid api key") || normalized.contains("token is invalid")
                || normalized.contains("30014")) {
            return "模型连接失败：硅基流动返回 Token 无效。请重新填写有效的硅基流动 API Key，不要填写 Bearer 前缀、引号或其他平台的 Key";
        }
        if (normalized.contains("model does not exist") || normalized.contains("model not found")
                || normalized.contains("20012")) {
            return "模型连接失败：上游平台明确表示该模型当前不可用，请确认账号已开通该模型，或从平台模型列表复制当前可用 ID";
        }
        if (normalized.contains("ai service failed with http 404")) {
            return "模型连接失败：项目 AI 服务没有提供测试接口，请检查 AI 服务地址、服务版本和 /internal/llm/test 路由";
        }
        if (normalized.contains("404 page not found")) {
            return "模型连接失败：请求已到达上游，但接口路径不存在；请确认服务地址是 OpenAI 兼容根地址（例如 https://api.siliconflow.cn/v1），不要把 /chat/completions 重复填写进去";
        }
        if (normalized.contains("404") || normalized.contains("not found")) {
            return "模型连接失败：上游返回 404，但这不能直接证明模型 ID 错误。请检查服务地址路径、账号模型权限和上游原始响应：" + diagnosticDetail(detail);
        }
        if (normalized.contains("429") || normalized.contains("rate limit") || normalized.contains("quota")) {
            return "模型连接失败：提供方限流或额度不足，请检查账户余额、额度和请求频率";
        }
        if (normalized.contains("timeout") || normalized.contains("timed out")) {
            return "模型连接失败：请求超时，请检查服务地址、网络或提高请求超时配置";
        }
        if (normalized.contains("connection") || normalized.contains("connecterror")
                || normalized.contains("network") || normalized.contains("winerror 10013")
                || normalized.contains("套接字") || normalized.contains("socket")) {
            return "模型连接失败：AI 服务无法连接到提供方，请检查本机防火墙、安全软件、网络代理和 HTTPS 出站连接" + diagnosticDetail(detail);
        }
        if (detail.isBlank()) return "模型连接失败：未收到 AI 服务的诊断信息";
        return "模型连接失败：" + detail;
    }

    private String diagnosticDetail(String detail) {
        String normalized = detail.replaceAll("[\\r\\n\\t]+", " ").trim();
        if (normalized.length() > 360) return normalized.substring(0, 360) + "…";
        return normalized;
    }

    private String resolveCredential(Long projectId, Long userId, ModelConfigRequest request) {
        if (request.credential() != null && !request.credential().isBlank()) {
            return cipher.encrypt(request.credential().trim());
        }
        if (request.credentialSourceId() != null) {
            ModelConfig source = modelMapper.findById(request.credentialSourceId(), projectId, userId);
            String requestedAuthType = defaultValue(request.authType(), "API_KEY");
            if (source == null
                    || !source.getProvider().trim().equalsIgnoreCase(request.provider().trim())
                    || !source.getEndpoint().trim().equals(request.endpoint().trim())
                    || !source.getAuthType().trim().equalsIgnoreCase(requestedAuthType.trim())
                    || source.getCredentialCiphertext() == null
                    || source.getCredentialCiphertext().isBlank()) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "MODEL_CREDENTIAL_SOURCE_UNAVAILABLE", "选择的服务连接没有可复用的有效凭证");
            }
            return source.getCredentialCiphertext();
        }
        return null;
    }

    private String defaultValue(String value, String fallback) { return value == null || value.isBlank() ? fallback : value; }

    private String scope(String value) {
        String normalized = defaultValue(value, "TEAM").trim().toUpperCase();
        if (!"PERSONAL".equals(normalized) && !"TEAM".equals(normalized)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_CONFIG_SCOPE", "Configuration scope must be PERSONAL or TEAM");
        }
        return normalized;
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
            if (extraBody != null && (!(extraBody instanceof Map<?, ?>))) throw invalidModelConfig();
            String reasoning = String.valueOf(config.getOrDefault("reasoningEffort", "none"));
            if (!List.of("none", "low", "medium", "high").contains(reasoning)) throw invalidModelConfig();
            String structured = String.valueOf(config.getOrDefault("structuredOutputMethod", "json_schema"));
            if (!List.of("json_schema", "function_calling", "json_mode").contains(structured)) throw invalidModelConfig();
            return value;
        } catch (ApiException exception) { throw exception; }
        catch (Exception exception) { throw invalidModelConfig(); }
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
}
