package com.cuupe.backend.modules.agent.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.agent.dto.AgentAttachmentResponse;
import com.cuupe.backend.modules.agent.dto.AgentMessageRequest;
import com.cuupe.backend.modules.agent.dto.AgentRunAccepted;
import com.cuupe.backend.modules.agent.entity.AgentAttachment;
import com.cuupe.backend.modules.agent.entity.AgentChunk;
import com.cuupe.backend.modules.agent.entity.AgentMessage;
import com.cuupe.backend.modules.agent.entity.AgentRun;
import com.cuupe.backend.modules.agent.entity.AgentRunEvent;
import com.cuupe.backend.modules.agent.entity.AgentThread;
import com.cuupe.backend.modules.agent.mapper.AgentMapper;
import com.cuupe.backend.modules.storage.ObjectStorageService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class AgentService {
    private static final long MAX_ATTACHMENT_BYTES = 50L * 1024 * 1024;
    private static final Pattern WORDS = Pattern.compile("[\\p{L}\\p{N}]+");

    private final AgentMapper mapper;
    private final ObjectMapper objectMapper;
    private final ObjectStorageService objectStorageService;
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
        Thread.startVirtualThread(() -> runPipeline(acceptedRun, workspaceId, projectId, userId, content, attachments));

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

    public java.io.InputStream openAttachment(AgentAttachment attachment) throws Exception {
        if (attachment.getStorageKey() != null && !attachment.getStorageKey().isBlank()) {
            return objectStorageService.open(attachment.getStorageKey());
        }
        return new java.io.ByteArrayInputStream(attachment.getContent() == null ? new byte[0] : attachment.getContent());
    }

    private void runPipeline(AgentRun run, Long workspaceId, Long projectId, Long userId, String query, List<Map<String, Object>> attachments) {
        try {
            publish(run, "run.started", Map.of("type", "run.started", "runId", run.getRunKey()));
            publishStep(run, "plan", "整理问题", "已接收问题，准备检索当前项目资料。", "running");
            publishStep(run, "plan", "整理问题", "问题已进入项目资料检索流程。", "completed");

            publishStep(run, "search", "检索项目资料", "正在检索当前项目已建立索引的文本资料。", "running");
            List<ScoredChunk> matches = findMatches(workspaceId, projectId, userId, query);
            publishStep(run, "search", "检索项目资料", matches.isEmpty() ? "当前项目资料没有命中内容。" : "已完成项目资料检索。", "completed");

            publishStep(run, "evidence", "整理证据引用", "正在整理可追溯的原文片段。", "running");
            for (int index = 0; index < matches.size(); index++) {
                ScoredChunk match = matches.get(index);
                Map<String, Object> citation = new LinkedHashMap<>();
                citation.put("id", "citation-" + match.chunk().getId());
                citation.put("title", match.chunk().getAssetName());
                citation.put("source", match.chunk().getAssetName() + (match.chunk().getPageNumber() == null ? "" : " · 第" + match.chunk().getPageNumber() + "页"));
                citation.put("quote", quote(match.chunk().getContent()));
                citation.put("score", String.format(Locale.ROOT, "%.2f", Math.min(0.99, 0.55 + match.score() / 10.0)));
                citation.put("pageNumber", match.chunk().getPageNumber());
                publish(run, "citation.added", Map.of("type", "citation.added", "runId", run.getRunKey(), "citation", citation));
            }
            publishStep(run, "evidence", "整理证据引用", matches.isEmpty() ? "没有可展示的引用。" : "已整理 " + matches.size() + " 条项目证据。", "completed");

            publishStep(run, "synthesis", "生成常规回答", "正在根据检索结果整理回答文本。", "running");
            String answer = buildAnswer(query, matches, attachments);
            streamText(run, answer);
            mapper.updateMessage(run.getAssistantMessageId(), answer, "COMPLETED");
            publish(run, "message.completed", Map.of("type", "message.completed", "runId", run.getRunKey(), "messageId", findMessageKey(run.getAssistantMessageId())));
            publishStep(run, "synthesis", "生成常规回答", "回答已生成。", "completed");
            mapper.updateRun(run.getId(), "COMPLETED", null);
            publish(run, "run.completed", Map.of("type", "run.completed", "runId", run.getRunKey()));
            completeSubscribers(run.getRunKey());
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

    private List<ScoredChunk> findMatches(Long workspaceId, Long projectId, Long userId, String query) {
        List<AgentChunk> chunks = mapper.findProjectChunks(workspaceId, projectId, userId);
        return scoreChunks(chunks, query);
    }

    private List<ScoredChunk> scoreChunks(List<AgentChunk> chunks, String query) {
        String normalized = query.toLowerCase(Locale.ROOT);
        Set<String> terms = new LinkedHashSet<>();
        var matcher = WORDS.matcher(normalized);
        while (matcher.find()) terms.add(matcher.group());
        for (int index = 0; index + 1 < normalized.length(); index++) {
            char first = normalized.charAt(index);
            char second = normalized.charAt(index + 1);
            if (Character.isLetterOrDigit(first) && Character.isLetterOrDigit(second)) {
                terms.add(normalized.substring(index, index + 2));
            }
        }
        List<ScoredChunk> scored = new ArrayList<>();
        for (AgentChunk chunk : chunks) {
            String text = chunk.getContent() == null ? "" : chunk.getContent().toLowerCase(Locale.ROOT);
            int score = 0;
            for (String term : terms) if (text.contains(term)) score++;
            if (score > 0) scored.add(new ScoredChunk(chunk, score));
        }
        return scored.stream().sorted(Comparator.comparingInt(ScoredChunk::score).reversed()).limit(3).toList();
    }

    private String buildAnswer(String query, List<ScoredChunk> matches, List<Map<String, Object>> attachments) {
        StringBuilder answer = new StringBuilder();
        answer.append("已完成对当前项目资料的常规检索。\n\n");
        if (matches.isEmpty()) {
            answer.append("项目资料中没有命中与“").append(query).append("”相关的内容。\n");
            answer.append("当前回答不包含演示数据；请补充已建立索引的资料，或调整问题后重试。");
        } else {
            answer.append("围绕“").append(query).append("”找到 ").append(matches.size()).append(" 条相关证据：\n");
            for (int index = 0; index < matches.size(); index++) {
                answer.append(index + 1).append(". ").append(matches.get(index).chunk().getAssetName()).append("：")
                        .append(quote(matches.get(index).chunk().getContent())).append("\n");
            }
            answer.append("\n以上内容来自当前项目资料，引用可在右侧查看原文片段。模型调用尚未接入，因此本次仅返回检索与证据整理结果。");
        }
        if (!attachments.isEmpty()) answer.append("\n\n已接收 ").append(attachments.size()).append(" 个附件，附件内容已保存，可供后续 Agent 处理。");
        return answer.toString();
    }

    private void streamText(AgentRun run, String text) throws IOException {
        String messageId = findMessageKey(run.getAssistantMessageId());
        for (int offset = 0; offset < text.length();) {
            int end = Math.min(text.length(), offset + 18);
            String delta = text.substring(offset, end);
            publish(run, "message.delta", Map.of("type", "message.delta", "runId", run.getRunKey(), "messageId", messageId, "delta", delta));
            offset = end;
        }
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

    private record ScoredChunk(AgentChunk chunk, int score) {}
}
