package com.cuupe.backend.modules.settings.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.config.security.SecretCipher;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
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
    private final AiIndexingClient aiClient;
    private final ObjectMapper objectMapper;
    private final AuditLogService auditLogService;

    /** Project candidates include the current user, project creator and workspace defaults. */
    @GetMapping("/models")
    public Result<List<ModelConfig>> models(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication auth) {
        Long userId = userId(auth);
        memberAccess(workspaceId, projectId, userId);
        return Result.success(modelMapper.findForProject(workspaceId, projectId, projectMapper.findCreatorId(projectId), userId));
    }

    @GetMapping("/tools")
    public Result<List<ToolConfig>> tools(@PathVariable Long projectId, Authentication auth) {
        return Result.success(toolMapper.findByProject(projectId, userId(auth)));
    }

    @GetMapping("/local-tools")
    public Result<Map<String, Object>> localTools(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                                   Authentication auth) {
        Long currentUserId = userId(auth);
        memberAccess(workspaceId, projectId, currentUserId);
        try {
            return Result.success(aiClient.localTools());
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "LOCAL_TOOLS_UNAVAILABLE", "本地工具系统暂不可用，请检查 Python AI 服务是否已启动");
        }
    }

    @PostMapping("/local-tools/reload")
    public Result<Map<String, Object>> reloadLocalTools(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                                         Authentication auth) {
        Long currentUserId = userId(auth);
        writeAccess(workspaceId, projectId, currentUserId);
        try {
            return Result.success(aiClient.reloadLocalTools());
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "LOCAL_TOOLS_RELOAD_FAILED", "本地工具重载失败，请检查 Python AI 服务日志");
        }
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
        auditLogService.record(workspaceId, projectId, currentUserId, "TOOL_CONFIG_CREATED", "TOOL_CONFIG", config.getId(),
                Map.of("connectorType", config.getConnectorType(), "scope", config.getScope()));
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
        if (request.credential() != null && !request.credential().isBlank()) config.setCredentialCiphertext(cipher.encrypt(request.credential()));
        config.setConfig(defaultValue(request.config(), config.getConfig()));
        if (request.enabled() != null) config.setEnabled(request.enabled());
        config.setScope(scope);
        toolMapper.update(config);
        auditLogService.record(workspaceId, projectId, currentUserId, "TOOL_CONFIG_UPDATED", "TOOL_CONFIG", config.getId(),
                Map.of("connectorType", config.getConnectorType(), "scope", config.getScope()));
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

    private void accessForUpdate(Long workspaceId, Long projectId, Long userId, ToolConfig config, String scope) {
        if ("PERSONAL".equals(config.getScope()) && userId.equals(config.getCreatedBy()) && "PERSONAL".equals(scope)) {
            memberAccess(workspaceId, projectId, userId);
        } else {
            writeAccess(workspaceId, projectId, userId);
        }
    }

    private void memberAccess(Long workspaceId, Long projectId, Long userId) {
        if (projectMapper.findAccessibleById(workspaceId, projectId, userId) == null) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_SETTINGS_FORBIDDEN", "当前用户无权访问此项目");
        }
    }

    private void writeAccess(Long workspaceId, Long projectId, Long userId) {
        if (!projectMapper.hasWriteAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_SETTINGS_FORBIDDEN", "只有项目创建者或管理员可以修改共享设置");
        }
    }

    private ToolConfig requiredTool(Long id, Long projectId, Long userId) {
        ToolConfig config = toolMapper.findById(id, projectId, userId);
        if (config == null) throw new ApiException(HttpStatus.NOT_FOUND, "TOOL_CONFIG_NOT_FOUND", "工具配置不存在或无权访问");
        return config;
    }

    private String encrypt(String value) {
        return value == null || value.isBlank() ? null : cipher.encrypt(value.trim());
    }

    @SuppressWarnings("unchecked")
    private void rejectWebSearch(ToolConfigRequest request) {
        if ("WEB_SEARCH".equalsIgnoreCase(defaultValue(request.connectorType(), ""))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_USE_DEDICATED_SETTINGS", "联网搜索必须在独立的联网搜索设置中配置");
        }
        if (request.config() == null || request.config().isBlank()) return;
        try {
            Map<String, Object> config = objectMapper.readValue(request.config(), Map.class);
            if ("web_search".equalsIgnoreCase(String.valueOf(config.getOrDefault("purpose", "")))) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_USE_DEDICATED_SETTINGS", "联网搜索必须在独立的联网搜索设置中配置");
            }
        } catch (ApiException exception) {
            throw exception;
        } catch (Exception ignored) {
            // Tool validation handles malformed JSON downstream.
        }
    }

    private String defaultValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private String scope(String value) {
        String normalized = defaultValue(value, "TEAM").trim().toUpperCase();
        if (!"PERSONAL".equals(normalized) && !"TEAM".equals(normalized)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_CONFIG_SCOPE", "Configuration scope must be PERSONAL or TEAM");
        }
        return normalized;
    }
}
