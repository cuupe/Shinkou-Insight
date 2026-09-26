package com.cuupe.backend.modules.ai;

import com.cuupe.backend.config.security.SecretCipher;
import com.cuupe.backend.modules.settings.entity.ModelConfig;
import com.cuupe.backend.modules.settings.entity.WebSearchConfig;
import com.cuupe.backend.modules.settings.mapper.ModelConfigMapper;
import com.cuupe.backend.modules.settings.mapper.WebSearchConfigMapper;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class RuntimeConfigResolver {
    private final ModelConfigMapper modelMapper;
    private final ProjectMapper projectMapper;
    private final WebSearchConfigMapper webSearchMapper;
    private final SecretCipher cipher;
    private final ObjectMapper objectMapper;

    public Map<String, Object> resolve(Long workspaceId, Long projectId, Long userId, Map<String, Object> requested) {
        Map<String, Object> runtime = new LinkedHashMap<>();
        Long creatorId = projectMapper.findCreatorId(projectId);
        ModelConfig model = resolveModel(workspaceId, projectId, creatorId, userId,
                requested == null ? null : requested.get("modelConfigId"));
        if (model != null) runtime.put("model", modelPayload(model));
        WebSearchConfig webSearch = resolveWebSearch(projectId, userId);
        if (webSearch != null) runtime.put("webSearch", webPayload(webSearch));
        ModelConfig embedding = resolveEmbedding(workspaceId, projectId, creatorId, userId,
                requested == null ? null : requested.get("embeddingConfigId"));
        if (embedding != null) runtime.put("embedding", embeddingPayload(embedding));
        return runtime;
    }

    public Map<String, Object> resolveModelPayload(Long workspaceId, Long projectId, Long userId, Long modelId) {
        Long creatorId = projectMapper.findCreatorId(projectId);
        ModelConfig model = modelId == null
                ? modelMapper.findForRuntime(workspaceId, creatorId, userId).stream()
                .filter(candidate -> !isEmbedding(candidate))
                .findFirst().orElse(null)
                : modelMapper.findProjectVisibleById(modelId, workspaceId, projectId, creatorId, userId);
        if (model == null || !model.isEnabled() || isEmbedding(model)) return Map.of();
        return Map.of("model", modelPayload(model));
    }

    public Map<String, Object> resolveWorkspaceModelPayload(Long workspaceId, Long userId, Long modelId) {
        ModelConfig model = modelMapper.findVisibleById(modelId, workspaceId, userId);
        if (model == null || !model.isEnabled() || isEmbedding(model)) return Map.of();
        return Map.of("model", modelPayload(model));
    }

    public Map<String, Object> resolveWorkspaceEmbeddingPayload(Long workspaceId, Long userId, Long embeddingId) {
        ModelConfig embedding = modelMapper.findVisibleById(embeddingId, workspaceId, userId);
        if (embedding == null || !embedding.isEnabled() || !isExternalEmbedding(embedding)) return Map.of();
        return Map.of("embedding", embeddingPayload(embedding));
    }

    public Map<String, Object> resolveEmbeddingPayload(Long workspaceId, Long projectId, Long userId, Object embeddingId) {
        Long creatorId = projectMapper.findCreatorId(projectId);
        ModelConfig embedding = resolveEmbedding(workspaceId, projectId, creatorId, userId, embeddingId);
        if (embedding == null) return Map.of();
        return Map.of("embedding", embeddingPayload(embedding));
    }

    public Map<String, Object> resolveWebSearchPayload(Long projectId, Long userId) {
        WebSearchConfig webSearch = resolveWebSearch(projectId, userId);
        if (webSearch == null) return Map.of();
        return Map.of("webSearch", webPayload(webSearch));
    }

    private ModelConfig resolveModel(Long workspaceId, Long projectId, Long creatorId, Long userId, Object requestedId) {
        if (requestedId != null) {
            ModelConfig requested = modelMapper.findProjectVisibleById(asLong(requestedId), workspaceId, projectId, creatorId, userId);
            if (requested != null && requested.isEnabled() && !isEmbedding(requested)) return requested;
        }
        return modelMapper.findForRuntime(workspaceId, creatorId, userId).stream()
                .filter(model -> !isEmbedding(model))
                .findFirst()
                .orElse(null);
    }

    private ModelConfig resolveEmbedding(Long workspaceId, Long projectId, Long creatorId, Long userId, Object requestedId) {
        if (requestedId != null) {
            ModelConfig requested = modelMapper.findProjectVisibleById(asLong(requestedId), workspaceId, projectId, creatorId, userId);
            if (requested != null && requested.isEnabled() && isExternalEmbedding(requested)) return requested;
        }
        return modelMapper.findForRuntime(workspaceId, creatorId, userId).stream()
                .filter(this::isExternalEmbedding)
                .findFirst()
                .orElse(null);
    }

    private boolean isEmbedding(ModelConfig model) {
        Map<String, Object> config = parse(model.getConfig());
        return "EMBEDDING".equalsIgnoreCase(String.valueOf(config.getOrDefault("use", "")));
    }

    private boolean isExternalEmbedding(ModelConfig model) {
        if (!isEmbedding(model)) return false;
        Map<String, Object> config = parse(model.getConfig());
        String mode = String.valueOf(config.getOrDefault("mode", "openai"));
        return !"local".equalsIgnoreCase(mode) && !"hash".equalsIgnoreCase(mode);
    }

    private WebSearchConfig resolveWebSearch(Long projectId, Long userId) {
        WebSearchConfig configured = webSearchMapper.findByProject(projectId, userId);
        if (configured != null) return configured.isEnabled() ? configured : null;
        WebSearchConfig defaults = new WebSearchConfig();
        defaults.setProvider("duckduckgo");
        defaults.setBaseUrl("https://html.duckduckgo.com/html/");
        defaults.setLanguage("zh-hans");
        defaults.setEnabled(true);
        defaults.setHasCredential(true);
        return defaults;
    }

    private Map<String, Object> modelPayload(ModelConfig model) {
        Map<String, Object> config = parse(model.getConfig());
        String credential = decrypt(model.getCredentialCiphertext(), "模型");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("provider", model.getProvider());
        payload.put("baseUrl", model.getEndpoint());
        payload.put("apiKey", credential);
        payload.put("model", model.getModelId());
        payload.put("timeoutSeconds", number(config, "timeout", 60));
        payload.put("retries", integer(config, "retries", 2));
        payload.put("structuredOutputMethod", String.valueOf(config.getOrDefault("structuredOutputMethod", "json_schema")));
        Map<String, Object> generation = new LinkedHashMap<>();
        generation.put("temperature", decimal(config, "temperature", 0.3));
        generation.put("topP", decimal(config, "topP", 0.9));
        putIntegerIfPresent(generation, "topK", config.get("topK"));
        generation.put("maxTokens", integer(config, "maxTokens", 4096));
        generation.put("contextWindow", integer(config, "contextWindow", 128000));
        generation.put("frequencyPenalty", decimal(config, "frequencyPenalty", 0));
        generation.put("presencePenalty", decimal(config, "presencePenalty", 0));
        putIntegerIfPresent(generation, "seed", config.get("seed"));
        Object stop = config.get("stop");
        if (stop instanceof List<?> values) generation.put("stop", values.stream().map(String::valueOf).filter(value -> !value.isBlank()).limit(4).toList());
        String reasoning = String.valueOf(config.getOrDefault("reasoningEffort", "high"));
        if (List.of("none", "low", "medium", "high").contains(reasoning)) generation.put("reasoningEffort", reasoning);
        Object extraBody = config.get("extraBody");
        if (extraBody instanceof Map<?, ?> values) generation.put("extraBody", values);
        payload.put("generation", generation);
        return payload;
    }

    private Map<String, Object> embeddingPayload(ModelConfig model) {
        Map<String, Object> config = parse(model.getConfig());
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("mode", String.valueOf(config.getOrDefault("mode", "openai")));
        payload.put("baseUrl", model.getEndpoint());
        payload.put("apiKey", decrypt(model.getCredentialCiphertext(), "Embedding"));
        payload.put("model", model.getModelId());
        payload.put("dimension", number(config, "dimension", 1536));
        return payload;
    }

    private Map<String, Object> webPayload(WebSearchConfig tool) {
        Map<String, Object> payload = new LinkedHashMap<>();
        String provider = tool.getProvider() == null ? "duckduckgo" : tool.getProvider().toLowerCase();
        payload.put("provider", provider);
        payload.put("apiKey", "brave".equals(provider) ? decrypt(tool.getCredentialCiphertext(), "联网搜索") : "");
        payload.put("baseUrl", tool.getBaseUrl() == null || tool.getBaseUrl().isBlank() ? "https://html.duckduckgo.com/html/" : tool.getBaseUrl());
        payload.put("language", tool.getLanguage() == null || tool.getLanguage().isBlank() ? "zh-hans" : tool.getLanguage());
        return payload;
    }

    private String decrypt(String ciphertext, String name) {
        if (ciphertext == null || ciphertext.isBlank()) throw new IllegalStateException(name + "连接器缺少凭证");
        return cipher.decrypt(ciphertext).trim();
    }

    private Map<String, Object> parse(String value) {
        if (value == null || value.isBlank()) return Map.of();
        try { return objectMapper.readValue(value, new TypeReference<>() {}); }
        catch (Exception exception) { return Map.of(); }
    }

    private Number number(Map<String, Object> config, String key, int fallback) {
        Object value = config.get(key);
        if (value instanceof Number number) return number;
        try { return Double.parseDouble(String.valueOf(value)); } catch (Exception ignored) { return fallback; }
    }

    private Number decimal(Map<String, Object> config, String key, double fallback) {
        Object value = config.get(key);
        if (value instanceof Number number) return number;
        try { return Double.parseDouble(String.valueOf(value)); } catch (Exception ignored) { return fallback; }
    }

    private int integer(Map<String, Object> config, String key, int fallback) {
        Object value = config.get(key);
        if (value instanceof Number number) return Math.max(0, number.intValue());
        try { return Math.max(0, Integer.parseInt(String.valueOf(value))); } catch (Exception ignored) { return fallback; }
    }

    private void putIntegerIfPresent(Map<String, Object> target, String key, Object value) {
        if (value == null || String.valueOf(value).isBlank()) return;
        try { target.put(key, Math.max(0, Integer.parseInt(String.valueOf(value)))); } catch (Exception ignored) { }
    }

    private Long asLong(Object value) {
        try { return Long.valueOf(String.valueOf(value)); }
        catch (Exception ignored) { return null; }
    }
}
