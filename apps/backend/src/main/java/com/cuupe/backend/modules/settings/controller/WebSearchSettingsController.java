package com.cuupe.backend.modules.settings.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.config.security.SecretCipher;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.settings.dto.WebSearchConfigRequest;
import com.cuupe.backend.modules.settings.entity.WebSearchConfig;
import com.cuupe.backend.modules.settings.mapper.WebSearchConfigMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/** 联网搜索专用设置入口，刻意不复用 /tools。 */
@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/settings/web-search")
@RequiredArgsConstructor
public class WebSearchSettingsController {
    private final ProjectMapper projectMapper;
    private final WebSearchConfigMapper webSearchMapper;
    private final SecretCipher cipher;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final AiIndexingClient aiClient;
    private final AuditLogService auditLogService;

    @GetMapping
    public Result<WebSearchConfig> get(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication auth) {
        Long currentUserId = userId(auth);
        memberAccess(workspaceId, projectId, currentUserId);
        WebSearchConfig config = webSearchMapper.findByProject(projectId, currentUserId);
        return Result.success(config == null ? defaultConfig() : config);
    }

    @PutMapping
    public Result<WebSearchConfig> save(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                        @Valid @RequestBody WebSearchConfigRequest request, Authentication auth) {
        Long currentUserId = userId(auth);
        memberAccess(workspaceId, projectId, currentUserId);
        String provider = value(request.provider(), "brave").toLowerCase();
        if (!"brave".equals(provider) && !"multi".equals(provider) && !"hybrid".equals(provider)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_PROVIDER_UNSUPPORTED", "当前支持 Brave Search 或多源混合搜索");
        }
        String baseUrl = request.baseUrl().trim();
        if (!baseUrl.startsWith("http://") && !baseUrl.startsWith("https://")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_URL_INVALID", "联网搜索地址必须以 http:// 或 https:// 开头");
        }

        WebSearchConfig config = webSearchMapper.findByProject(projectId, currentUserId);
        boolean creating = config == null;
        boolean keyRequired = "brave".equals(provider);
        if (keyRequired && (request.apiKey() == null || request.apiKey().isBlank())
                && (config == null || config.getCredentialCiphertext() == null || config.getCredentialCiphertext().isBlank())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_CREDENTIAL_REQUIRED", "Brave Search 必须填写 API Key");
        }
        if (creating) {
            config = new WebSearchConfig();
            config.setProjectId(projectId);
            config.setCreatedBy(currentUserId);
        }
        config.setProvider(provider);
        config.setBaseUrl(baseUrl);
        config.setLanguage(value(request.language(), "zh-hans"));
        if (request.apiKey() != null && !request.apiKey().isBlank()) {
            config.setCredentialCiphertext(cipher.encrypt(request.apiKey().trim()));
        }
        config.setEnabled(request.enabled() == null || request.enabled());
        if (creating) {
            webSearchMapper.insert(config);
        } else {
            webSearchMapper.update(config);
        }
        auditLogService.record(workspaceId, projectId, currentUserId,
                "WEB_SEARCH_CONFIG_UPDATED", "WEB_SEARCH_CONFIG", config.getId(), Map.of("provider", provider, "enabled", config.isEnabled()));
        return Result.success(webSearchMapper.findByProject(projectId, currentUserId));
    }

    @PostMapping("/test")
    @SuppressWarnings("unchecked")
    public Result<Map<String, Object>> test(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication auth) {
        Long currentUserId = userId(auth);
        memberAccess(workspaceId, projectId, currentUserId);
        try {
            Map<String, Object> payload = runtimeConfigResolver.resolveWebSearchPayload(projectId, currentUserId);
            if (payload.isEmpty()) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_CONFIG_UNAVAILABLE", "请先保存并启用联网搜索配置");
            }
            return Result.success(aiClient.testWebSearch((Map<String, Object>) payload.get("webSearch")));
        } catch (ApiException exception) {
            throw exception;
        } catch (IllegalStateException exception) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WEB_SEARCH_CREDENTIAL_INVALID", "无法读取联网搜索 API Key，请重新保存配置");
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "WEB_SEARCH_CONNECTION_FAILED", "联网搜索连接测试失败，请检查地址、API Key 和网络");
        }
    }

    private Long userId(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("Current session does not contain user information");
    }

    private void memberAccess(Long workspaceId, Long projectId, Long userId) {
        if (projectMapper.findAccessibleById(workspaceId, projectId, userId) == null) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_SETTINGS_FORBIDDEN", "Current user cannot access this project");
        }
    }

    private String value(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private WebSearchConfig defaultConfig() {
        WebSearchConfig config = new WebSearchConfig();
        config.setProvider("duckduckgo");
        config.setBaseUrl("https://html.duckduckgo.com/html/");
        config.setLanguage("zh-hans");
        config.setEnabled(true);
        // Public DuckDuckGo search is usable without storing a secret.
        config.setHasCredential(true);
        return config;
    }
}
