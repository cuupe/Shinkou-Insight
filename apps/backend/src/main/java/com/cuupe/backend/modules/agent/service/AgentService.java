package com.cuupe.backend.modules.agent.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.agent.dto.AgentAttachmentResponse;
import com.cuupe.backend.modules.agent.dto.AgentMessageRequest;
import com.cuupe.backend.modules.agent.dto.AgentRunAccepted;
import com.cuupe.backend.modules.agent.entity.AgentAttachment;
import com.cuupe.backend.modules.agent.entity.AgentMessage;
import com.cuupe.backend.modules.agent.entity.AgentRun;
import com.cuupe.backend.modules.agent.entity.AgentRunEvent;
import com.cuupe.backend.modules.agent.entity.AgentThread;
import com.cuupe.backend.modules.agent.mapper.AgentMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.settings.entity.PromptVersion;
import com.cuupe.backend.modules.settings.mapper.PromptVersionMapper;
import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import com.cuupe.backend.modules.storage.ObjectStorageService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Service
@RequiredArgsConstructor
public class AgentService {
    private static final long MAX_ATTACHMENT_BYTES = 50L * 1024 * 1024;

    private final AgentMapper mapper;
    private final ObjectMapper objectMapper;
    private final ObjectStorageService objectStorageService;
    private final AiIndexingClient aiClient;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final PromptVersionMapper promptVersionMapper;
    private final WorkspaceMapper workspaceMapper;
    private final Map<String, CopyOnWriteArrayList<SseEmitter>> subscribers = new ConcurrentHashMap<>();

    public AgentRunAccepted accept(Long workspaceId, Long projectId, Long userId, AgentMessageRequest request) {
        if (!mapper.hasProjectAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        String content = clean(request.getContent());
        if (content.isBlank()) throw ApiException.badRequest("VALIDATION_ERROR", "问题内容不能为空");
        if (content.length() > 20000) throw ApiException.badRequest("CONTENT_TOO_LARGE", "问题内容不能超过 20000 个字符");

        List<Map<String, Object>> attachments = request.getAttachments() == null ? List.of() : request.getAttachments();
        if (attachments.size() > 10) throw ApiException.badRequest("TOO_MANY_ATTACHMENTS", "一次最多上传 10 个附件");
        for (Map<String, Object> attachment : attachments) validateAttachmentReference(workspaceId, projectId, userId, attachment);

        String threadKey = safeKey(request.getThreadId(), "thread-" + UUID.randomUUID());
        String messageKey = safeKey(request.getMessageId(), "message-" + UUID.randomUUID());
        AgentThread thread = mapper.findThread(threadKey, projectId, userId);
        if (thread == null) {
            thread = new AgentThread();
            thread.setWorkspaceId(workspaceId);
            thread.setProjectId(projectId);
            thread.setCreatedBy(userId);
            thread.setThreadKey(threadKey);
            thread.setTitle(shortText(content, 80));
            mapper.insertThread(thread);
        } else {
            mapper.touchThread(thread.getId(), shortText(content, 80));
        }

        AgentMessage userMessage = message(thread.getId(), messageKey + "-user", "USER", content, "COMPLETED", request.getAttachments());
        AgentMessage assistantMessage = message(thread.getId(), messageKey, "ASSISTANT", "", "STREAMING", List.of());
        mapper.insertMessage(userMessage);
        mapper.insertMessage(assistantMessage);

        AgentRun run = new AgentRun();
        run.setRunKey("agent-run-" + UUID.randomUUID());
        run.setThreadId(thread.getId());
        run.setUserMessageId(userMessage.getId());
        run.setAssistantMessageId(assistantMessage.getId());
        run.setStatus("RUNNING");
        mapper.insertRun(run);

        AgentRun acceptedRun = run;
        Thread.startVirtualThread(() -> runPipeline(acceptedRun, workspaceId, projectId, userId, content, request));

        return new AgentRunAccepted(
                run.getRunKey(),
                messageKey,
                "RUNNING",
                "/api/workspaces/" + workspaceId + "/projects/" + projectId + "/agent/runs/" + run.getRunKey() + "/events"
        );
    }

    public SseEmitter subscribe(Long workspaceId, Long projectId, Long userId, String runKey, Long afterId) {
        AgentRun run = mapper.findRun(runKey, projectId, userId);
        if (run == null) throw new ApiException(HttpStatus.NOT_FOUND, "AGENT_RUN_NOT_FOUND", "Agent 运行不存在或无权访问");

        SseEmitter emitter = new SseEmitter(0L);
        CopyOnWriteArrayList<SseEmitter> runSubscribers = subscribers.computeIfAbsent(runKey, ignored -> new CopyOnWriteArrayList<>());
        runSubscribers.add(emitter);
        Runnable remove = () -> removeSubscriber(runKey, emitter);
        emitter.onCompletion(remove);
        emitter.onTimeout(remove);
        emitter.onError(ignored -> remove.run());

        try {
            for (AgentRunEvent event : mapper.findEvents(runKey, afterId)) send(emitter, event);
            AgentRun current = mapper.findRun(runKey, projectId, userId);
            if (current != null && isTerminal(current.getStatus())) {
                emitter.complete();
                remove.run();
            }
        } catch (IOException exception) {
            remove.run();
            emitter.completeWithError(exception);
        }
        return emitter;
    }

    public AgentAttachmentResponse uploadAttachment(Long workspaceId, Long projectId, Long userId, MultipartFile file) throws Exception {
        if (!mapper.hasProjectAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        if (file == null || file.isEmpty()) throw ApiException.badRequest("EMPTY_FILE", "附件不能为空");
        if (file.getSize() > MAX_ATTACHMENT_BYTES) throw ApiException.badRequest("FILE_TOO_LARGE", "附件不能超过 50 MB");

        AgentAttachment attachment = new AgentAttachment();
        attachment.setWorkspaceId(workspaceId);
        attachment.setProjectId(projectId);
        attachment.setUploadedBy(userId);
        attachment.setFileName(safeFileName(file.getOriginalFilename()));
        attachment.setKind(kindOf(file.getContentType(), file.getOriginalFilename()));
        attachment.setMimeType(file.getContentType() == null ? MediaType.APPLICATION_OCTET_STREAM_VALUE : file.getContentType());
        attachment.setFileSize(file.getSize());
        String storageKey = "workspaces/" + workspaceId + "/projects/" + projectId + "/agent/" + UUID.randomUUID() + "/" + attachment.getFileName();
        try (var input = file.getInputStream()) {
            objectStorageService.put(storageKey, input, file.getSize(), attachment.getMimeType());
        }
        attachment.setStorageKey(storageKey);
        try {
            mapper.insertAttachment(attachment);
        } catch (RuntimeException exception) {
            try { objectStorageService.remove(storageKey); } catch (Exception ignored) { }
            throw exception;
        }
        String url = "/api/workspaces/" + workspaceId + "/projects/" + projectId + "/agent/attachments/" + attachment.getId() + "/content";
        return new AgentAttachmentResponse(attachment.getId(), attachment.getFileName(), attachment.getKind(), attachment.getMimeType(), attachment.getFileSize(), url);
    }

    public AgentAttachment getAttachment(Long workspaceId, Long projectId, Long userId, Long attachmentId) {
        AgentAttachment attachment = mapper.findAttachment(attachmentId, workspaceId, projectId, userId);
        if (attachment == null) throw new ApiException(HttpStatus.NOT_FOUND, "ATTACHMENT_NOT_FOUND", "附件不存在或无权访问");
        return attachment;
    }

    @SuppressWarnings("unchecked")
    public void handleAiCallback(String runKey, Map<String, Object> body) {
        Long projectId = longValue(body.get("projectId"));
        Long userId = longValue(body.get("userId"));
        if (projectId == null || userId == null) return;
        AgentRun run = mapper.findRun(runKey, projectId, userId);
        if (run == null) return;
        String eventType = String.valueOf(body.getOrDefault("eventType", ""));
        Map<String, Object> payload = body.get("payload") instanceof Map<?, ?> value
                ? (Map<String, Object>) value : Map.of();
        try {
            if (eventType.startsWith("node.")) {
                String node = String.valueOf(payload.getOrDefault("node", "agent"));
                String status = eventType.endsWith("started") ? "running" : "completed";
                publishStep(run, node.toLowerCase(Locale.ROOT), String.valueOf(payload.getOrDefault("title", node)), String.valueOf(payload.getOrDefault("detail", "")), status);
                return;
            }
            if (eventType.startsWith("tool.")) {
                String tool = String.valueOf(payload.getOrDefault("tool", "tool"));
                publishStep(run, "tool", "调用 " + tool, String.valueOf(payload.getOrDefault("query", "")), eventType.endsWith("started") ? "running" : "completed");
                return;
            }
            if ("evidence.added".equals(eventType)) {
                Object items = payload.get("items");
                if (items instanceof List<?> list) for (Object raw : list) publishCitation(run, raw);
                return;
            }
            if ("run.completed".equals(eventType)) {
                String answer = formatReport(payload.get("report"));
                mapper.updateMessage(run.getAssistantMessageId(), answer, "COMPLETED");
                publish(run, "message.delta", Map.of("type", "message.delta", "runId", runKey, "messageId", findMessageKey(run.getAssistantMessageId()), "delta", answer));
                publish(run, "message.completed", Map.of("type", "message.completed", "runId", runKey, "messageId", findMessageKey(run.getAssistantMessageId())));
                mapper.updateRun(run.getId(), "COMPLETED", null);
                publish(run, "run.completed", Map.of("type", "run.completed", "runId", runKey));
                completeSubscribers(runKey);
                return;
            }
            if ("run.failed".equals(eventType)) {
                String message = String.valueOf(payload.getOrDefault("message", "Agent 运行失败"));
                mapper.updateMessage(run.getAssistantMessageId(), message, "FAILED");
                mapper.updateRun(run.getId(), "FAILED", message);
                publish(run, "run.failed", Map.of("type", "run.failed", "runId", runKey, "message", message));
                completeSubscribers(runKey);
            }
        } catch (IOException exception) {
            mapper.updateRun(run.getId(), "FAILED", "Agent 事件转发失败");
            completeSubscribers(runKey);
        }
    }

    public void cancel(Long workspaceId, Long projectId, Long userId, String runKey) {
        if (!mapper.hasProjectAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        AgentRun run = mapper.findRun(runKey, projectId, userId);
        if (run == null) throw new ApiException(HttpStatus.NOT_FOUND, "AGENT_RUN_NOT_FOUND", "Agent 运行不存在或无权访问");
        try { aiClient.cancelRun(runKey); } catch (Exception exception) { throw new ApiException(HttpStatus.BAD_GATEWAY, "AGENT_CANCEL_FAILED", "Agent 运行取消失败"); }
        mapper.updateMessage(run.getAssistantMessageId(), "本次运行已取消。", "COMPLETED");
        mapper.updateRun(run.getId(), "CANCELLED", null);
        try {
            String messageId = findMessageKey(run.getAssistantMessageId());
            publish(run, "message.delta", Map.of("type", "message.delta", "runId", runKey, "messageId", messageId, "delta", "本次运行已取消。"));
            publish(run, "message.completed", Map.of("type", "message.completed", "runId", runKey, "messageId", messageId));
            publish(run, "run.completed", Map.of("type", "run.completed", "runId", runKey));
        } catch (IOException exception) {
            completeSubscribers(runKey);
        }
        completeSubscribers(runKey);
    }

    public java.io.InputStream openAttachment(AgentAttachment attachment) throws Exception {
        if (attachment.getStorageKey() != null && !attachment.getStorageKey().isBlank()) {
            return objectStorageService.open(attachment.getStorageKey());
        }
        return new java.io.ByteArrayInputStream(attachment.getContent() == null ? new byte[0] : attachment.getContent());
    }

    private void runPipeline(AgentRun run, Long workspaceId, Long projectId, Long userId, String query, AgentMessageRequest request) {
        try {
            Map<String, Object> config = new LinkedHashMap<>();
            putIfPresent(config, "allowWebSearch", request.getAllowWebSearch());
            putIfPresent(config, "maxResearchRounds", request.getMaxResearchRounds());
            putIfPresent(config, "topK", request.getTopK());
            putIfPresent(config, "retrievalMode", request.getRetrievalMode());
            putIfPresent(config, "useReranker", request.getUseReranker());
            putIfPresent(config, "outputLanguage", request.getOutputLanguage());
            Map<String, String> systemPrompts = activeSystemPrompts(workspaceId, userId);
            if (!systemPrompts.isEmpty()) config.put("systemPrompts", systemPrompts);
            config.putAll(agentPolicy(workspaceId, userId));
            Map<String, Object> requested = new LinkedHashMap<>();
            putIfPresent(requested, "modelConfigId", request.getModelConfigId());
            putIfPresent(requested, "webSearchToolId", request.getWebSearchToolId());
            Map<String, Object> runtime = runtimeConfigResolver.resolve(projectId, userId, requested);
            aiClient.executeAgentRun(run.getRunKey(), workspaceId, projectId, userId, findMessageKey(run.getAssistantMessageId()), query, config, runtime);
        } catch (Exception exception) {
            String message = exception.getMessage() == null ? "Agent 运行失败" : shortText(exception.getMessage(), 900);
            mapper.updateMessage(run.getAssistantMessageId(), message, "FAILED");
            mapper.updateRun(run.getId(), "FAILED", message);
            try {
                publish(run, "run.failed", Map.of("type", "run.failed", "runId", run.getRunKey(), "message", message));
            } catch (Exception ignored) {
                // The persisted FAILED status remains the source of truth if the stream itself is unavailable.
            }
            completeSubscribers(run.getRunKey());
        }
    }

    private Map<String, String> activeSystemPrompts(Long workspaceId, Long userId) {
        Map<String, String> prompts = new LinkedHashMap<>();
        for (PromptVersion prompt : promptVersionMapper.findByWorkspace(workspaceId, userId)) {
            if (!"ACTIVE".equalsIgnoreCase(clean(prompt.getStatus()))) continue;
            String scene = clean(prompt.getScene()).toLowerCase(Locale.ROOT);
            String systemPrompt = clean(prompt.getSystemPrompt());
            if (scene.isBlank() || systemPrompt.isBlank()) continue;
            // The mapper returns the newest versions first, so the first active
            // version wins if old data contains duplicate active rows.
            prompts.putIfAbsent(scene, systemPrompt);
        }
        return prompts;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> agentPolicy(Long workspaceId, Long userId) {
        Workspace workspace = workspaceMapper.findAccessible(workspaceId, userId);
        if (workspace == null || workspace.getPreferences() == null || workspace.getPreferences().isBlank()) return Map.of();
        try {
            Map<String, Object> preferences = objectMapper.readValue(workspace.getPreferences(), Map.class);
            Object raw = preferences.get("agentPolicy");
            if (!(raw instanceof Map<?, ?> policy)) return Map.of();
            Map<String, Object> result = new LinkedHashMap<>();
            if (policy.get("maxCalls") != null) result.put("toolMaxCalls", policy.get("maxCalls"));
            if (policy.get("requireApproval") != null) result.put("requireToolApproval", policy.get("requireApproval"));
            return result;
        } catch (Exception ignored) { return Map.of(); }
    }

    private void putIfPresent(Map<String, Object> target, String key, Object value) {
        if (value != null) target.put(key, value);
    }

    private void publishStep(AgentRun run, String kind, String title, String detail, String status) throws IOException {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("id", run.getRunKey() + "-" + kind);
        event.put("kind", kind);
        event.put("title", title);
        event.put("detail", detail);
        event.put("status", status);
        publish(run, "event.updated", Map.of("type", "event.updated", "runId", run.getRunKey(), "event", event));
    }

    private void publishCitation(AgentRun run, Object raw) throws IOException {
        if (!(raw instanceof Map<?, ?> item)) return;
        String id = String.valueOf(value(item, "id", "evidence"));
        String title = String.valueOf(valueAny(item, "assetName", "asset_name", valueAny(item, "sourceName", "source_name", "外部来源")));
        String source = String.valueOf(valueAny(item, "sourceName", "source_name", title));
        Object page = valueAny(item, "pageNumber", "page_number", null);
        Map<String, Object> citation = new LinkedHashMap<>();
        citation.put("id", id);
        citation.put("title", title);
        citation.put("source", source + (page == null ? "" : " · 第" + page + "页"));
        citation.put("quote", quote(String.valueOf(value(item, "content", ""))));
        citation.put("score", value(item, "score", null));
        citation.put("pageNumber", page);
        citation.put("url", item.get("url"));
        publish(run, "citation.added", Map.of("type", "citation.added", "runId", run.getRunKey(), "citation", citation));
    }

    private Object value(Map<?, ?> source, String key, Object fallback) {
        Object value = source.get(key);
        return value == null ? fallback : value;
    }

    private Object valueAny(Map<?, ?> source, String first, String second, Object fallback) {
        return value(source, first, value(source, second, fallback));
    }

    @SuppressWarnings("unchecked")
    private String formatReport(Object raw) {
        if (!(raw instanceof Map<?, ?> report)) return String.valueOf(raw == null ? "Agent 未返回报告" : raw);
        StringBuilder answer = new StringBuilder();
        appendLine(answer, report.get("title"));
        appendLine(answer, valueAny(report, "executiveSummary", "executive_summary", null));
        Object sections = report.get("sections");
        if (sections instanceof List<?> list) for (Object section : list) {
            if (!(section instanceof Map<?, ?> value)) continue;
            appendLine(answer, value.get("heading"));
            appendLine(answer, value.get("body"));
        }
        Object recommendations = report.get("recommendations");
        if (recommendations instanceof List<?> list && !list.isEmpty()) {
            appendLine(answer, "建议");
            for (Object item : list) appendLine(answer, "- " + item);
        }
        return answer.length() == 0 ? "Agent 已完成分析，但报告内容为空。" : answer.toString().trim();
    }

    private void appendLine(StringBuilder target, Object value) {
        if (value != null && !String.valueOf(value).isBlank()) target.append(String.valueOf(value)).append("\n\n");
    }

    private Long longValue(Object value) {
        if (value == null) return null;
        try { return Long.valueOf(String.valueOf(value)); } catch (NumberFormatException ignored) { return null; }
    }

    private AgentMessage message(Long threadId, String key, String role, String content, String status, List<Map<String, Object>> attachments) {
        AgentMessage message = new AgentMessage();
        message.setThreadId(threadId);
        message.setClientMessageId(key);
        message.setRole(role);
        message.setContent(content);
        message.setStatus(status);
        try {
            message.setAttachments(objectMapper.writeValueAsString(attachments == null ? List.of() : attachments));
        } catch (Exception exception) {
            throw ApiException.badRequest("INVALID_ATTACHMENTS", "附件信息格式不正确");
        }
        return message;
    }

    private void publish(AgentRun run, String eventType, Map<String, Object> payload) throws IOException {
        AgentRunEvent event = new AgentRunEvent();
        event.setRunId(run.getId());
        event.setEventType(eventType);
        try {
            event.setPayload(objectMapper.writeValueAsString(payload));
        } catch (Exception exception) {
            throw new IOException("Agent 事件序列化失败", exception);
        }
        mapper.insertEvent(event);
        for (SseEmitter emitter : subscribers.getOrDefault(run.getRunKey(), new CopyOnWriteArrayList<>())) {
            try {
                send(emitter, event);
            } catch (IOException exception) {
                removeSubscriber(run.getRunKey(), emitter);
            }
        }
    }

    @SuppressWarnings("unchecked")
    private void send(SseEmitter emitter, AgentRunEvent event) throws IOException {
        try {
            Map<String, Object> payload = objectMapper.readValue(event.getPayload(), Map.class);
            emitter.send(SseEmitter.event().id(String.valueOf(event.getId())).data(payload));
        } catch (RuntimeException exception) {
            throw new IOException("Agent SSE 推送失败", exception);
        }
    }

    private String findMessageKey(Long messageId) {
        return mapper.findMessageKey(messageId);
    }

    private void completeSubscribers(String runKey) {
        CopyOnWriteArrayList<SseEmitter> current = subscribers.remove(runKey);
        if (current != null) current.forEach(SseEmitter::complete);
    }

    private void removeSubscriber(String runKey, SseEmitter emitter) {
        CopyOnWriteArrayList<SseEmitter> current = subscribers.get(runKey);
        if (current == null) return;
        current.remove(emitter);
        if (current.isEmpty()) subscribers.remove(runKey, current);
    }

    private boolean isTerminal(String status) {
        return "COMPLETED".equals(status) || "FAILED".equals(status);
    }

    private String safeKey(String value, String fallback) {
        String key = clean(value);
        if (key.isBlank() || key.length() > 120 || !key.matches("[A-Za-z0-9._:-]+")) return fallback;
        return key;
    }

    private String clean(String value) {
        return value == null ? "" : value.trim();
    }

    private String shortText(String value, int max) {
        String cleaned = value == null ? "" : value;
        return cleaned.length() <= max ? cleaned : cleaned.substring(0, max);
    }

    private String quote(String value) {
        String cleaned = value == null ? "" : value.replaceAll("\\s+", " ").trim();
        return shortText(cleaned, 260);
    }

    private String kindOf(String mimeType, String fileName) {
        String mime = mimeType == null ? "" : mimeType.toLowerCase(Locale.ROOT);
        if (mime.startsWith("image/")) return "image";
        if (mime.startsWith("video/")) return "video";
        if (mime.startsWith("audio/")) return "audio";
        if (mime.contains("pdf") || extension(fileName).equals("pdf")) return "pdf";
        return "file";
    }

    private void validateAttachmentReference(Long workspaceId, Long projectId, Long userId, Map<String, Object> attachment) {
        Object uploadId = attachment == null ? null : attachment.get("uploadId");
        if (uploadId == null) throw ApiException.badRequest("INVALID_ATTACHMENT", "消息附件缺少上传凭证");
        try {
            Long id = Long.valueOf(String.valueOf(uploadId));
            if (!mapper.hasAttachmentAccess(id, workspaceId, projectId, userId)) {
                throw new ApiException(HttpStatus.NOT_FOUND, "ATTACHMENT_NOT_FOUND", "附件不存在或无权访问");
            }
        } catch (NumberFormatException exception) {
            throw ApiException.badRequest("INVALID_ATTACHMENT", "消息附件上传凭证不正确");
        }
    }

    private String safeFileName(String value) {
        String name = value == null || value.isBlank() ? "attachment" : value;
        name = name.replaceAll("[\\r\\n\\\\/]", "_").trim();
        return shortText(name.isBlank() ? "attachment" : name, 255);
    }

    private String extension(String fileName) {
        if (fileName == null || !fileName.contains(".")) return "";
        return fileName.substring(fileName.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

}
