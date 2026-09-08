package com.cuupe.backend.modules.ai;

import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import tools.jackson.databind.ObjectMapper;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class AiIndexingClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient client;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final String internalApiKey;
    private final String callbackBaseUrl;

    public AiIndexingClient(
            ObjectMapper objectMapper,
            @Value("${shinkou.ai.base-url:http://localhost:8000}") String baseUrl,
            @Value("${shinkou.ai.internal-api-key:local-dev-key}") String internalApiKey,
            @Value("${shinkou.ai.callback-base-url:http://localhost:8081}") String callbackBaseUrl
    ) {
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.internalApiKey = internalApiKey;
        this.callbackBaseUrl = callbackBaseUrl.replaceAll("/+$", "");
        this.client = new OkHttpClient.Builder().callTimeout(Duration.ofSeconds(90)).build();
    }

    public void index(KnowledgeAsset asset, Long workspaceId, Long userId, Map<String, Object> runtimeEmbedding) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("assetId", asset.getId());
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", asset.getProjectId());
        payload.put("userId", userId);
        payload.put("fileName", asset.getName());
        payload.put("mimeType", asset.getMimeType());
        payload.put("storageKey", asset.getStorageKey());
        payload.put("language", asset.getLanguage());
        payload.put("checksum", asset.getChecksum());
        if (runtimeEmbedding != null && !runtimeEmbedding.isEmpty()) payload.put("runtimeEmbedding", runtimeEmbedding.get("embedding"));

        Request request = new Request.Builder()
                .url(baseUrl + "/internal/indexing/assets/" + asset.getId())
                .header("X-Internal-Api-Key", internalApiKey)
                .post(RequestBody.create(objectMapper.writeValueAsBytes(payload), JSON))
                .build();
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("AI indexing failed with HTTP " + response.code());
            }
        }
    }

    public Map<String, Object> knowledge(String path, Map<String, Object> payload) throws IOException {
        return post(path, payload);
    }

    public void executeRun(Long runId, Long workspaceId, Long projectId, Long userId, String goal, String config, Map<String, Object> runtime) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("runId", runId);
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", projectId);
        payload.put("userId", userId);
        payload.put("goal", goal);
        try {
            payload.put("config", objectMapper.readValue(config == null ? "{}" : config, Map.class));
        } catch (Exception exception) {
            payload.put("config", Map.of());
        }
        if (runtime != null && !runtime.isEmpty()) payload.put("runtimeModel", runtime.get("model"));
        if (runtime != null && runtime.get("webSearch") != null) payload.put("runtimeWebSearch", runtime.get("webSearch"));
        if (runtime != null && runtime.get("embedding") != null) payload.put("runtimeEmbedding", runtime.get("embedding"));
        payload.put("callback", Map.of("eventEndpoint", callbackBaseUrl + "/internal/ai/runs/" + runId + "/callback"));
        post("/internal/research/runs/" + runId + "/execute", payload);
    }

    public void executeAgentRun(String runKey, Long workspaceId, Long projectId, Long userId, String messageId, String goal, Map<String, Object> config, Map<String, Object> runtime) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("runId", runKey);
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", projectId);
        payload.put("userId", userId);
        payload.put("goal", goal);
        payload.put("agentMessageId", messageId);
        payload.put("config", config == null ? Map.of() : config);
        if (runtime != null && runtime.get("model") != null) payload.put("runtimeModel", runtime.get("model"));
        if (runtime != null && runtime.get("webSearch") != null) payload.put("runtimeWebSearch", runtime.get("webSearch"));
        if (runtime != null && runtime.get("embedding") != null) payload.put("runtimeEmbedding", runtime.get("embedding"));
        payload.put("callback", Map.of("eventEndpoint", callbackBaseUrl + "/internal/ai/agent-runs/" + runKey + "/callback"));
        post("/internal/research/runs/" + runKey + "/execute", payload);
    }

    public void cancelRun(Long runId) throws IOException {
        cancelRun(String.valueOf(runId));
    }

    public void cancelRun(String runId) throws IOException {
        post("/internal/research/runs/" + runId + "/cancel", Map.of());
    }

    public Map<String, Object> testModel(Map<String, Object> model) throws IOException {
        return post("/internal/llm/test", model);
    }

    public Map<String, Object> testEmbedding(Map<String, Object> embedding) throws IOException {
        return post("/internal/embedding/test", embedding);
    }

    public Map<String, Object> runSecurityHarness(Long workspaceId, Long projectId, List<String> caseIds,
                                                   boolean includeModelProbes, Map<String, Object> runtime) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", projectId);
        payload.put("caseIds", caseIds == null ? List.of() : caseIds);
        payload.put("includeModelProbes", includeModelProbes);
        if (runtime != null && runtime.get("model") != null) payload.put("runtimeModel", runtime.get("model"));
        return post("/internal/security-harness/run", payload);
    }

    private Map<String, Object> post(String path, Map<String, Object> payload) throws IOException {
        Request request = new Request.Builder()
                .url(baseUrl + path)
                .header("X-Internal-Api-Key", internalApiKey)
                .post(RequestBody.create(objectMapper.writeValueAsBytes(payload), JSON))
                .build();
        try (Response response = client.newCall(request).execute()) {
            String body = response.body() == null ? "{}" : response.body().string();
            if (!response.isSuccessful()) throw new IOException("AI service failed with HTTP " + response.code());
            return objectMapper.readValue(body, Map.class);
        }
    }
}
