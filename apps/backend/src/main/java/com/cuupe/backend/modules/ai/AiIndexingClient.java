package com.cuupe.backend.modules.ai;

import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import com.cuupe.backend.common.exception.ApiException;
import tools.jackson.databind.ObjectMapper;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.Dispatcher;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.http.HttpStatus;

import java.io.IOException;
import java.util.Base64;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class AiIndexingClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient client;
    private final OkHttpClient indexingClient;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final String internalApiKey;
    private final String callbackBaseUrl;

    public AiIndexingClient(
            ObjectMapper objectMapper,
            @Value("${shinkou.ai.base-url:http://localhost:8003}") String baseUrl,
            @Value("${shinkou.ai.internal-api-key:local-dev-key}") String internalApiKey,
            @Value("${shinkou.ai.callback-base-url:http://localhost:8080}") String callbackBaseUrl,
            @Value("${shinkou.ai.indexing-timeout-seconds:600}") long indexingTimeoutSeconds
    ) {
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.internalApiKey = internalApiKey;
        this.callbackBaseUrl = callbackBaseUrl.replaceAll("/+$", "");
        Dispatcher dispatcher = new Dispatcher();
        dispatcher.setMaxRequests(128);
        dispatcher.setMaxRequestsPerHost(64);
        this.client = new OkHttpClient.Builder()
                .dispatcher(dispatcher)
                .connectTimeout(Duration.ofSeconds(10))
                .readTimeout(Duration.ofSeconds(90))
                .callTimeout(Duration.ofSeconds(90))
                .build();
        Duration indexingTimeout = Duration.ofSeconds(Math.max(1, indexingTimeoutSeconds));
        this.indexingClient = client.newBuilder()
                .readTimeout(indexingTimeout)
                .callTimeout(indexingTimeout)
                .build();
    }

    public void index(KnowledgeAsset asset, Long workspaceId, Long userId, Map<String, Object> runtimeEmbedding, String chunkingConfig) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("assetId", asset.getId());
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", asset.getProjectId());
        payload.put("userId", userId);
        // A display name may have no extension. The parser needs the original
        // stored filename to select the PDF/Office/text decoder.
        String storageKey = asset.getStorageKey();
        payload.put("fileName", storageKey == null || storageKey.isBlank()
                ? asset.getName() : storageKey.substring(storageKey.lastIndexOf('/') + 1));
        payload.put("mimeType", asset.getMimeType());
        payload.put("storageKey", asset.getStorageKey());
        payload.put("language", asset.getLanguage());
        payload.put("checksum", asset.getChecksum());
        if (runtimeEmbedding != null && !runtimeEmbedding.isEmpty()) payload.put("runtimeEmbedding", runtimeEmbedding.get("embedding"));
        if (chunkingConfig != null && !chunkingConfig.isBlank()) {
            try {
                payload.put("chunking", objectMapper.readValue(chunkingConfig, Map.class));
            } catch (Exception ignored) {
                // A malformed persisted preference must fall back to the AI service defaults.
            }
        }

        Request request = new Request.Builder()
                .url(baseUrl + "/internal/indexing/assets/" + asset.getId())
                .header("X-Internal-Api-Key", internalApiKey)
                .post(RequestBody.create(objectMapper.writeValueAsBytes(payload), JSON))
                .build();
        try (Response response = indexingClient.newCall(request).execute()) {
            String body = response.body() == null ? "{}" : response.body().string();
            if (!response.isSuccessful()) throw knowledgeError(response.code(), body);
            Map<String, Object> result = objectMapper.readValue(body, Map.class);
            if (!(result.get("chunkCount") instanceof Number count) || count.intValue() <= 0) {
                throw new IOException("文件未生成可检索的文本片段，请检查文件内容或 OCR 识别结果");
            }
        } catch (java.io.InterruptedIOException exception) {
            throw new IOException("资料索引超过等待时间，请稍后重新索引或缩小文件后重试", exception);
        }
    }

    public Map<String, Object> knowledge(String path, Map<String, Object> payload) throws IOException {
        try {
            Request request = new Request.Builder().url(baseUrl + path)
                    .header("X-Internal-Api-Key", internalApiKey)
                    .post(RequestBody.create(objectMapper.writeValueAsBytes(payload), JSON)).build();
            try (Response response = client.newCall(request).execute()) {
                String body = response.body() == null ? "{}" : response.body().string();
                if (!response.isSuccessful()) {
                    HttpStatus status = response.code() == 422 ? HttpStatus.UNPROCESSABLE_ENTITY : HttpStatus.BAD_GATEWAY;
                    throw new ApiException(status, "KNOWLEDGE_SERVICE_ERROR", knowledgeError(response.code(), body).getMessage());
                }
                return objectMapper.readValue(body, Map.class);
            }
        } catch (java.io.InterruptedIOException exception) {
            throw new ApiException(HttpStatus.GATEWAY_TIMEOUT, "KNOWLEDGE_TIMEOUT", "知识库检索超时，请稍后重试或检查嵌入模型连接");
        } catch (IOException exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "KNOWLEDGE_UNAVAILABLE", "知识库服务暂时无法连接，请检查 Python 服务后重试");
        }
    }

    private IOException knowledgeError(int status, String body) {
        String message = "知识库处理失败（HTTP " + status + "），请检查 Python 服务日志";
        try {
            Map<String, Object> error = objectMapper.readValue(body, Map.class);
            // Never forward HTML error pages or validation input values.
            if ((status >= 400 && status < 500 || status == 503) && error.get("detail") instanceof String detail && !detail.isBlank()) {
                message = detail.length() > 500 ? detail.substring(0, 500) : detail;
            }
        } catch (RuntimeException ignored) { }
        return new IOException(message);
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

    public void executeAgentRun(String runKey, Long workspaceId, Long projectId, Long userId, String messageId, String goal, Map<String, Object> config, Map<String, Object> runtime, Map<String, Object> projectContext, List<Map<String, Object>> contextMessages, List<Map<String, Object>> attachments) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("runId", runKey);
        payload.put("workspaceId", workspaceId);
        payload.put("projectId", projectId);
        payload.put("userId", userId);
        payload.put("goal", goal);
        payload.put("agentMessageId", messageId);
        payload.put("projectContext", projectContext == null ? Map.of() : projectContext);
        payload.put("contextMessages", contextMessages == null ? List.of() : contextMessages);
        payload.put("attachments", attachments == null ? List.of() : attachments);
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

    public Map<String, Object> updatePlan(String runId, Map<String, Object> payload) throws IOException {
        return patch("/internal/research/runs/" + runId + "/plan", payload);
    }

    public Map<String, Object> testModel(Map<String, Object> model) throws IOException {
        return post("/internal/llm/test", model);
    }

    public Map<String, Object> modelContext(Map<String, Object> model) throws IOException {
        return post("/internal/llm/context", model);
    }

    public Map<String, Object> testEmbedding(Map<String, Object> embedding) throws IOException {
        return post("/internal/embedding/test", embedding);
    }

    public Map<String, Object> testWebSearch(Map<String, Object> webSearch) throws IOException {
        return post("/internal/web-search/test", webSearch);
    }

    public Map<String, Object> previewFile(String fileName, String mimeType, byte[] data) throws IOException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("fileName", fileName == null ? "attachment" : fileName);
        payload.put("mimeType", mimeType == null ? "application/octet-stream" : mimeType);
        payload.put("data", Base64.getEncoder().encodeToString(data == null ? new byte[0] : data));
        return post("/internal/files/preview", payload);
    }

    public Map<String, Object> validateWebSource(String url, String title, String excerpt) throws IOException {
        return post("/internal/web-source/validate", Map.of(
                "url", url == null ? "" : url,
                "title", title == null ? "" : title,
                "excerpt", excerpt == null ? "" : excerpt
        ));
    }

    public Map<String, Object> runDetail(String runId) throws IOException {
        return get("/internal/research/runs/" + runId, client.newBuilder().callTimeout(Duration.ofSeconds(4)).build());
    }

    public Map<String, Object> localTools() throws IOException {
        Map<String, Object> result = get("/internal/tools");
        result.put("files", get("/internal/files/tools"));
        return result;
    }

    public Map<String, Object> reloadLocalTools() throws IOException {
        post("/internal/tools/custom/reload", Map.of());
        return localTools();
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
            if (!response.isSuccessful()) {
                String detail = body.replaceAll("[\\r\\n\\t]+", " ").trim();
                if (detail.length() > 1600) detail = detail.substring(0, 1600) + "…";
                throw new IOException("AI service failed with HTTP " + response.code() + " at " + request.url()
                        + (detail.isBlank() ? "" : ": " + detail));
            }
            return objectMapper.readValue(body, Map.class);
        }
    }

    private Map<String, Object> get(String path) throws IOException {
        return get(path, client);
    }

    private Map<String, Object> get(String path, OkHttpClient requestClient) throws IOException {
        Request request = new Request.Builder()
                .url(baseUrl + path)
                .header("X-Internal-Api-Key", internalApiKey)
                .get()
                .build();
        try (Response response = requestClient.newCall(request).execute()) {
            String body = response.body() == null ? "{}" : response.body().string();
            if (!response.isSuccessful()) {
                String detail = body.replaceAll("[\\r\\n\\t]+", " ").trim();
                if (detail.length() > 1600) detail = detail.substring(0, 1600) + "…";
                throw new IOException("AI service failed with HTTP " + response.code() + " at " + request.url()
                        + (detail.isBlank() ? "" : ": " + detail));
            }
            return objectMapper.readValue(body, Map.class);
        }
    }

    private Map<String, Object> patch(String path, Map<String, Object> payload) throws IOException {
        Request request = new Request.Builder()
                .url(baseUrl + path)
                .header("X-Internal-Api-Key", internalApiKey)
                .patch(RequestBody.create(objectMapper.writeValueAsBytes(payload), JSON))
                .build();
        try (Response response = client.newCall(request).execute()) {
            String body = response.body() == null ? "{}" : response.body().string();
            if (!response.isSuccessful()) {
                String detail = body.replaceAll("[\\r\\n\\t]+", " ").trim();
                if (detail.length() > 1600) detail = detail.substring(0, 1600) + "…";
                throw new IOException("AI service failed with HTTP " + response.code() + " at " + request.url()
                        + (detail.isBlank() ? "" : ": " + detail));
            }
            return objectMapper.readValue(body, Map.class);
        }
    }
}
