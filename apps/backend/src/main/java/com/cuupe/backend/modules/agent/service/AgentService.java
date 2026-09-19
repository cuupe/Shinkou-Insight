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
import com.cuupe.backend.modules.agent.entity.AgentTokenUsage;
import com.cuupe.backend.modules.agent.mapper.AgentMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import com.cuupe.backend.modules.storage.ObjectStorageService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
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
    private final WorkspaceMapper workspaceMapper;
    private final Map<String, CopyOnWriteArrayList<SseEmitter>> subscribers = new ConcurrentHashMap<>();
    private final Set<String> streamedMessageRuns = ConcurrentHashMap.newKeySet();
    private final Map<String, Set<String>> receivedUpstreamEvents = new ConcurrentHashMap<>();
    private final Map<String, Object> callbackLocks = new ConcurrentHashMap<>();

    public AgentRunAccepted accept(Long workspaceId, Long projectId, Long userId, AgentMessageRequest request) {
        if (!mapper.hasProjectAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        String content = clean(request.getContent());
        if (content.isBlank()) throw ApiException.badRequest("VALIDATION_ERROR", "问题内容不能为空");
        if (content.length() > 20000) throw ApiException.badRequest("CONTENT_TOO_LARGE", "问题内容不能超过 20000 个字符");
        validateGeneration(request);

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
            thread.setTitle(summarizeThreadTitle(content));
            mapper.insertThread(thread);
        } else {
            AgentMessage firstUserMessage = mapper.findFirstUserMessage(thread.getId(), projectId, userId);
            String title = firstUserMessage == null
                    ? (thread.getTitle() == null || thread.getTitle().isBlank() ? summarizeThreadTitle(content) : thread.getTitle())
                    : summarizeThreadTitle(firstUserMessage.getContent());
            mapper.touchThread(thread.getId(), title);
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

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> history(Long projectId, Long userId) {
        List<Map<String, Object>> result = new java.util.ArrayList<>();
        for (AgentThread thread : mapper.findThreads(projectId, userId)) {
            List<Map<String, Object>> messages = new java.util.ArrayList<>();
            for (AgentMessage message : mapper.findMessages(thread.getId(), projectId, userId)) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("id", message.getClientMessageId());
                item.put("role", "ASSISTANT".equalsIgnoreCase(message.getRole()) ? "assistant" : "user");
                item.put("content", message.getContent());
                item.put("status", "FAILED".equalsIgnoreCase(message.getStatus()) ? "failed" : "completed");
                item.put("createdAt", message.getCreatedAt());
                try {
                    item.put("attachments", objectMapper.readValue(message.getAttachments() == null ? "[]" : message.getAttachments(), List.class));
                } catch (Exception ignored) {
                    item.put("attachments", List.of());
                }
                messages.add(item);
            }
            Map<String, List<Map<String, Object>>> citationsByMessage = new LinkedHashMap<>();
            Map<String, Map<String, Object>> citations = new LinkedHashMap<>();
            Map<String, Map<String, Object>> timeline = new LinkedHashMap<>();
            List<Map<String, Object>> eventHistory = new java.util.ArrayList<>();
            Map<String, Object> tokenUsage = null;
            Map<String, Object> contextUsage = null;
            List<AgentRun> runs = mapper.findRunsByThread(thread.getId());
            AgentRun latestRun = runs.isEmpty() ? null : runs.get(runs.size() - 1);
            for (AgentRun run : runs) {
                String messageKey = findMessageKey(run.getAssistantMessageId());
                if (messageKey == null) continue;
                for (AgentRunEvent event : mapper.findEvents(run.getRunKey(), null)) {
                    try {
                        Map<String, Object> payload = objectMapper.readValue(event.getPayload(), Map.class);
                        boolean latest = latestRun != null && run.getRunKey().equals(latestRun.getRunKey());
                        if (latest && "event.updated".equals(event.getEventType())) {
                            Object rawEvent = payload.get("event");
                            if (rawEvent instanceof Map<?, ?> value && value.get("id") != null) {
                                Map<String, Object> eventSnapshot = new LinkedHashMap<>();
                                for (Map.Entry<?, ?> entry : value.entrySet()) {
                                    eventSnapshot.put(String.valueOf(entry.getKey()), entry.getValue());
                                }
                                Map<String, Object> metadata = new LinkedHashMap<>();
                                if (eventSnapshot.get("meta") instanceof Map<?, ?> rawMeta) {
                                    for (Map.Entry<?, ?> entry : rawMeta.entrySet()) {
                                        metadata.put(String.valueOf(entry.getKey()), entry.getValue());
                                    }
                                }
                                metadata.put("eventId", event.getId());
                                metadata.put("sequence", eventHistory.size() + 1);
                                eventSnapshot.put("meta", metadata);
                                eventHistory.add(eventSnapshot);
                                timeline.put(String.valueOf(value.get("id")), eventSnapshot);
                            }
                        }
                        if ("citation.added".equals(event.getEventType())) {
                            Object citation = payload.get("citation");
                            if (citation instanceof Map<?, ?> raw && raw.get("id") != null) {
                                Map<String, Object> citationMap = (Map<String, Object>) raw;
                                citations.put(String.valueOf(raw.get("id")), citationMap);
                                citationsByMessage.computeIfAbsent(messageKey, ignored -> new java.util.ArrayList<>())
                                        .add(citationMap);
                            }
                        }
                        if (latest && "run.completed".equals(event.getEventType())) {
                            Object rawUsage = payload.get("usage");
                            Object rawContext = payload.get("contextCompression");
                            if (rawUsage instanceof Map<?, ?> value) tokenUsage = normalizeTokenUsage(value);
                            if (rawContext instanceof Map<?, ?> value) contextUsage = normalizeContextUsage(value);
                        }
                    } catch (Exception ignored) {
                        // A malformed historical event must not hide the conversation itself.
                    }
                }
            }
            if (latestRun != null && tokenUsage == null) {
                AgentTokenUsage storedUsage = mapper.findTokenUsage(latestRun.getRunKey());
                if (storedUsage != null && hasStoredTokenUsage(storedUsage)) {
                    tokenUsage = new LinkedHashMap<>();
                    putIfPresent(tokenUsage, "inputTokens", storedUsage.getInputTokens());
                    putIfPresent(tokenUsage, "outputTokens", storedUsage.getOutputTokens());
                    putIfPresent(tokenUsage, "totalTokens", storedUsage.getTotalTokens());
                    putIfPresent(tokenUsage, "model", storedUsage.getModelName());
                    tokenUsage.put("available", true);
                    if (contextUsage == null && ((storedUsage.getCompressedContextTokens() != null && storedUsage.getCompressedContextTokens() > 0)
                            || (storedUsage.getContextMessageCount() != null && storedUsage.getContextMessageCount() > 0))) {
                        contextUsage = new LinkedHashMap<>();
                        putIfPresent(contextUsage, "compressedContextTokens", storedUsage.getCompressedContextTokens());
                        putIfPresent(contextUsage, "finalMessageCount", storedUsage.getContextMessageCount());
                    }
                }
            }
            for (Map<String, Object> message : messages) {
                Object messageId = message.get("id");
                if (messageId != null && citationsByMessage.containsKey(String.valueOf(messageId))) {
                    message.put("citations", citationsByMessage.get(String.valueOf(messageId)));
                }
            }
            String title = thread.getTitle();
            for (Map<String, Object> message : messages) {
                if ("user".equals(message.get("role")) && !String.valueOf(message.getOrDefault("content", "")).isBlank()) {
                    title = summarizeThreadTitle(String.valueOf(message.get("content")));
                    break;
                }
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", thread.getThreadKey());
            item.put("title", title == null || title.isBlank() ? "新的问题整理" : title);
            item.put("preview", messages.isEmpty() ? "等待输入第一个问题" : shortText(String.valueOf(messages.get(messages.size() - 1).get("content")), 120));
            item.put("updatedAt", thread.getUpdatedAt());
            item.put("messageCount", messages.size());
            item.put("messages", messages);
            item.put("events", new java.util.ArrayList<>(timeline.values()));
            item.put("eventHistory", eventHistory);
            item.put("citations", new java.util.ArrayList<>(citations.values()));
            item.put("status", latestRun == null ? "idle" : "FAILED".equalsIgnoreCase(latestRun.getStatus()) ? "failed" : "RUNNING".equalsIgnoreCase(latestRun.getStatus()) ? "running" : "completed");
            item.put("runId", latestRun == null ? null : latestRun.getRunKey());
            if (latestRun != null && latestRun.getStartedAt() != null) {
                item.put("runStartedAt", latestRun.getStartedAt().toString());
            }
            if (latestRun != null && latestRun.getFinishedAt() != null) {
                item.put("runFinishedAt", latestRun.getFinishedAt().toString());
                if (latestRun.getStartedAt() != null) {
                    item.put("runDurationMs", Math.max(0L, Duration.between(latestRun.getStartedAt(), latestRun.getFinishedAt()).toMillis()));
                }
            }
            if (tokenUsage != null) item.put("tokenUsage", tokenUsage);
            if (contextUsage != null) item.put("contextUsage", contextUsage);
            result.add(item);
        }
        return result;
    }

    @Transactional
    public void deleteThread(Long workspaceId, Long projectId, Long userId, String threadKey) {
        if (!mapper.hasProjectAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        AgentThread thread = mapper.findThread(threadKey, projectId, userId);
        if (thread == null || !workspaceId.equals(thread.getWorkspaceId())) {
            throw new ApiException(HttpStatus.NOT_FOUND, "AGENT_THREAD_NOT_FOUND", "对话不存在或无权访问");
        }
        if (mapper.hasRunningRun(thread.getId())) {
            throw ApiException.conflict("AGENT_THREAD_RUNNING", "请先停止正在运行的 Agent 对话");
        }
        if (mapper.deleteThread(thread.getId(), workspaceId, projectId, userId) == 0) {
            throw new ApiException(HttpStatus.NOT_FOUND, "AGENT_THREAD_NOT_FOUND", "对话不存在或无权访问");
        }
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
        Object callbackLock = callbackLocks.computeIfAbsent(runKey, ignored -> new Object());
        synchronized (callbackLock) {
            handleAiCallbackLocked(runKey, body);
        }
    }

    @SuppressWarnings("unchecked")
    private void handleAiCallbackLocked(String runKey, Map<String, Object> body) {
        Long projectId = longValue(body.get("projectId"));
        Long userId = longValue(body.get("userId"));
        if (projectId == null || userId == null) return;
        AgentRun run = mapper.findRun(runKey, projectId, userId);
        if (run == null) return;
        String eventType = String.valueOf(body.getOrDefault("eventType", ""));
        // A late callback from a retried/recovered worker must never append to
        // a message that has already been finalized.
        if (isTerminal(run.getStatus())) return;
        String upstreamEventId = String.valueOf(body.getOrDefault("eventId", "")).trim();
        if (!upstreamEventId.isBlank()) {
            Set<String> seen = receivedUpstreamEvents.computeIfAbsent(runKey, ignored -> ConcurrentHashMap.newKeySet());
            if (!seen.add(upstreamEventId)) return;
        }
        Map<String, Object> payload = body.get("payload") instanceof Map<?, ?> value
                ? (Map<String, Object>) value : Map.of();
        try {
            if ("run.started".equals(eventType)) {
                Map<String, Object> started = new LinkedHashMap<>();
                started.put("type", "run.started");
                started.put("runId", runKey);
                if (payload.get("startedAt") != null) started.put("startedAt", payload.get("startedAt"));
                publish(run, "run.started", started);
                return;
            }
            if ("usage.updated".equals(eventType)) {
                Map<String, Object> usage = new LinkedHashMap<>();
                usage.put("type", "usage.updated");
                usage.put("runId", runKey);
                if (payload.get("usage") != null) usage.put("usage", payload.get("usage"));
                if (payload.get("latencyMs") != null) usage.put("latencyMs", payload.get("latencyMs"));
                if (payload.get("delta") != null) usage.put("delta", payload.get("delta"));
                publish(run, "usage.updated", usage);
                return;
            }
            if (eventType.startsWith("node.")) {
                String node = String.valueOf(payload.getOrDefault("node", "agent"));
                String status = eventType.endsWith("started") ? "running" : "completed";
                String kind = "ATTACHMENT_ANALYSIS".equalsIgnoreCase(node) ? "file" : node.toLowerCase(Locale.ROOT);
                publishStep(run, kind, String.valueOf(payload.getOrDefault("title", node)), String.valueOf(payload.getOrDefault("detail", "")), status, payload);
                return;
            }
            if (eventType.startsWith("tool.")) {
                String tool = String.valueOf(payload.getOrDefault("tool", "tool"));
                String detail;
                if (payload.get("detail") != null) {
                    detail = String.valueOf(payload.get("detail"));
                } else if (payload.get("count") != null) {
                    detail = "已获得 " + payload.get("count") + " 条结果";
                } else {
                    detail = String.valueOf(payload.getOrDefault("query", ""));
                }
                publishStep(run, "tool", "调用 " + tool, detail, eventType.endsWith("started") ? "running" : "completed");
                return;
            }
            if ("evidence.added".equals(eventType)) {
                Object items = payload.get("items");
                if (items instanceof List<?> list) {
                    publishStep(run, "evidence", "整理证据", "已收集 " + list.size() + " 条可引用来源", "completed");
                    for (Object raw : list) publishCitation(run, raw);
                }
                return;
            }
            if ("artifact.added".equals(eventType)) {
                publishArtifact(run, body, payload);
                return;
            }
            if ("message.delta".equals(eventType)) {
                String messageId = findMessageKey(run.getAssistantMessageId());
                String delta = String.valueOf(payload.getOrDefault("delta", ""));
                if (!delta.isBlank()) {
                    streamedMessageRuns.add(runKey);
                    publish(run, "message.delta", Map.of(
                            "type", "message.delta",
                            "runId", runKey,
                            "messageId", messageId,
                            "delta", delta
                    ));
                }
                return;
            }
            if ("message.replace".equals(eventType)) {
                streamedMessageRuns.add(runKey);
                publish(run, "message.replace", Map.of(
                        "type", "message.replace",
                        "runId", runKey,
                        "messageId", findMessageKey(run.getAssistantMessageId()),
                        "content", String.valueOf(payload.getOrDefault("content", ""))
                ));
                return;
            }
            if ("run.completed".equals(eventType)) {
                Object rawArtifacts = payload.get("artifacts");
                if (rawArtifacts instanceof List<?> artifacts) {
                    for (Object rawArtifact : artifacts) {
                        if (!(rawArtifact instanceof Map<?, ?>)) continue;
                        Map<String, Object> artifactPayload = new LinkedHashMap<>();
                        artifactPayload.put("artifact", rawArtifact);
                        artifactPayload.put("messageId", findMessageKey(run.getAssistantMessageId()));
                        try {
                            publishArtifact(run, body, artifactPayload);
                        } catch (IOException ignored) {
                            // The artifact event relay may already have persisted this file.
                        }
                    }
                }
                String answer = formatReport(payload.get("report"));
                saveTokenUsage(run, body, payload);
                mapper.updateMessage(run.getAssistantMessageId(), answer, "COMPLETED");
                if (!streamedMessageRuns.remove(runKey)) {
                    // Compatibility fallback for an older AI service that does not emit deltas.
                    publish(run, "message.delta", Map.of("type", "message.delta", "runId", runKey, "messageId", findMessageKey(run.getAssistantMessageId()), "delta", answer));
                }
                publish(run, "message.completed", Map.of("type", "message.completed", "runId", runKey, "messageId", findMessageKey(run.getAssistantMessageId())));
                mapper.updateRun(run.getId(), "COMPLETED", null);
                Map<String, Object> completion = new LinkedHashMap<>();
                completion.put("type", "run.completed");
                completion.put("runId", runKey);
                if (payload.get("usage") != null) completion.put("usage", payload.get("usage"));
                if (payload.get("contextCompression") != null) completion.put("contextCompression", payload.get("contextCompression"));
                if (payload.get("startedAt") != null) completion.put("startedAt", payload.get("startedAt"));
                if (payload.get("durationMs") != null) completion.put("durationMs", payload.get("durationMs"));
                if (payload.get("strategy") != null) completion.put("strategy", payload.get("strategy"));
                if (payload.get("multiAgent") != null) completion.put("multiAgent", payload.get("multiAgent"));
                publish(run, "run.completed", completion);
                completeSubscribers(runKey);
                receivedUpstreamEvents.remove(runKey);
                callbackLocks.remove(runKey);
                return;
            }
            if ("run.failed".equals(eventType)) {
                String message = String.valueOf(payload.getOrDefault("message", "Agent 运行失败"));
                mapper.updateMessage(run.getAssistantMessageId(), message, "FAILED");
                mapper.updateRun(run.getId(), "FAILED", message);
                streamedMessageRuns.remove(runKey);
                publish(run, "run.failed", Map.of("type", "run.failed", "runId", runKey, "message", message));
                completeSubscribers(runKey);
                receivedUpstreamEvents.remove(runKey);
                callbackLocks.remove(runKey);
            }
        } catch (IOException exception) {
            mapper.updateRun(run.getId(), "FAILED", "Agent 事件转发失败");
            completeSubscribers(runKey);
            receivedUpstreamEvents.remove(runKey);
            callbackLocks.remove(runKey);
        }
    }

    public void cancel(Long workspaceId, Long projectId, Long userId, String runKey) {
        if (!mapper.hasProjectAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        AgentRun run = mapper.findRun(runKey, projectId, userId);
        if (run == null) throw new ApiException(HttpStatus.NOT_FOUND, "AGENT_RUN_NOT_FOUND", "Agent 运行不存在或无权访问");
        if (run.getStatus() != null && !"RUNNING".equalsIgnoreCase(run.getStatus())) return;
        try {
            aiClient.cancelRun(runKey);
        } catch (IOException exception) {
            // The AI service keeps active runs in memory. If it was restarted,
            // the durable Java run can outlive the in-memory AI run. Treat that
            // missing upstream run as an idempotent cancellation and reconcile
            // the durable state below; real upstream/network failures remain 502.
            String detail = exception.getMessage();
            if (detail == null || !detail.contains("HTTP 404")) {
                throw new ApiException(HttpStatus.BAD_GATEWAY, "AGENT_CANCEL_FAILED", "Agent 运行取消失败");
            }
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AGENT_CANCEL_FAILED", "Agent 运行取消失败");
        }
        mapper.updateMessage(run.getAssistantMessageId(), "本次运行已取消。", "COMPLETED");
        mapper.updateRun(run.getId(), "CANCELLED", null);
        streamedMessageRuns.remove(runKey);
        receivedUpstreamEvents.remove(runKey);
        callbackLocks.remove(runKey);
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
            putIfPresent(config, "reflectionEnabled", request.getReflectionEnabled());
            putIfPresent(config, "strategy", request.getStrategy());
            putIfPresent(config, "multiAgentMode", request.getMultiAgentMode());
            putIfPresent(config, "maxResearchRounds", request.getMaxResearchRounds());
            putIfPresent(config, "topK", request.getTopK());
            putIfPresent(config, "retrievalMode", request.getRetrievalMode());
            putIfPresent(config, "useReranker", request.getUseReranker());
            putIfPresent(config, "outputLanguage", request.getOutputLanguage());
            putIfPresent(config, "temperature", request.getTemperature());
            putIfPresent(config, "topP", request.getTopP());
            putIfPresent(config, "modelTopK", request.getModelTopK());
            putIfPresent(config, "maxTokens", request.getMaxTokens());
            putIfPresent(config, "frequencyPenalty", request.getFrequencyPenalty());
            putIfPresent(config, "reasoningEffort", request.getReasoningEffort());
            config.putAll(agentPolicy(workspaceId, userId));
            Map<String, Object> requested = new LinkedHashMap<>();
            putIfPresent(requested, "modelConfigId", request.getModelConfigId());
            Map<String, Object> runtime = runtimeConfigResolver.resolve(workspaceId, projectId, userId, requested);
            // 只有本次运行明确开启联网搜索时，才把独立搜索凭证传给 AI 服务。
            if (!Boolean.TRUE.equals(request.getAllowWebSearch())) runtime.remove("webSearch");
            // 没有项目级模型时，仍把本次生成参数作为独立覆盖传给 AI 服务默认模型。
            if (!runtime.containsKey("model")) {
                Map<String, Object> generation = new LinkedHashMap<>();
                putIfPresent(generation, "temperature", request.getTemperature());
                putIfPresent(generation, "topP", request.getTopP());
                putIfPresent(generation, "topK", request.getModelTopK());
                putIfPresent(generation, "maxTokens", request.getMaxTokens());
                putIfPresent(generation, "frequencyPenalty", request.getFrequencyPenalty());
                putIfPresent(generation, "reasoningEffort", request.getReasoningEffort());
                if (!generation.isEmpty()) config.put("generation", generation);
            }
            applyGenerationOverrides(runtime, request);
            aiClient.executeAgentRun(run.getRunKey(), workspaceId, projectId, userId, findMessageKey(run.getAssistantMessageId()), query, config, runtime, request.getContextMessages(), attachmentPayload(workspaceId, projectId, userId, request.getAttachments()));
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

    @SuppressWarnings("unchecked")
    private Map<String, Object> agentPolicy(Long workspaceId, Long userId) {
        Workspace workspace = workspaceMapper.findAccessible(workspaceId, userId);
        if (workspace == null || workspace.getPreferences() == null || workspace.getPreferences().isBlank()) return Map.of();
        try {
            Map<String, Object> preferences = objectMapper.readValue(workspace.getPreferences(), Map.class);
            Object raw = preferences.get("agentPolicy");
            Map<String, Object> result = new LinkedHashMap<>();
            if (raw instanceof Map<?, ?> policy) {
                if (policy.get("maxCalls") != null) result.put("toolMaxCalls", policy.get("maxCalls"));
                if (policy.get("requireApproval") != null) result.put("requireToolApproval", policy.get("requireApproval"));
            }
            Object localTools = preferences.get("localTools");
            if (localTools instanceof Map<?, ?> configuredTools) {
                List<String> disabledTools = new java.util.ArrayList<>();
                for (Map.Entry<?, ?> entry : configuredTools.entrySet()) {
                    if (Boolean.FALSE.equals(entry.getValue())) disabledTools.add(String.valueOf(entry.getKey()));
                }
                if (!disabledTools.isEmpty()) result.put("disabledTools", disabledTools);
            }
            return result;
        } catch (Exception ignored) { return Map.of(); }
    }

    private void putIfPresent(Map<String, Object> target, String key, Object value) {
        if (value != null) target.put(key, value);
    }

    @SuppressWarnings("unchecked")
    private void applyGenerationOverrides(Map<String, Object> runtime, AgentMessageRequest request) {
        Object rawModel = runtime.get("model");
        if (!(rawModel instanceof Map<?, ?>)) return;
        Map<String, Object> model = (Map<String, Object>) rawModel;
        Map<String, Object> generation = model.get("generation") instanceof Map<?, ?> existing
                ? new LinkedHashMap<>((Map<String, Object>) existing)
                : new LinkedHashMap<>();
        putIfPresent(generation, "temperature", request.getTemperature());
        putIfPresent(generation, "topP", request.getTopP());
        putIfPresent(generation, "topK", request.getModelTopK());
        putIfPresent(generation, "maxTokens", request.getMaxTokens());
        putIfPresent(generation, "frequencyPenalty", request.getFrequencyPenalty());
        putIfPresent(generation, "reasoningEffort", request.getReasoningEffort());
        model.put("generation", generation);
        runtime.put("model", model);
    }

    private void validateGeneration(AgentMessageRequest request) {
        if (request.getTopK() != null && (request.getTopK() < 1 || request.getTopK() > 20)) {
            throw ApiException.badRequest("INVALID_RETRIEVAL_TOP_K", "检索 Top-K 必须在 1 到 20 之间");
        }
        if (request.getTemperature() != null && (request.getTemperature() < 0 || request.getTemperature() > 2)) {
            throw ApiException.badRequest("INVALID_TEMPERATURE", "Temperature 必须在 0 到 2 之间");
        }
        if (request.getTopP() != null && (request.getTopP() <= 0 || request.getTopP() > 1)) {
            throw ApiException.badRequest("INVALID_TOP_P", "Top-P 必须大于 0 且不超过 1");
        }
        if (request.getModelTopK() != null && (request.getModelTopK() < 1 || request.getModelTopK() > 1000)) {
            throw ApiException.badRequest("INVALID_MODEL_TOP_K", "模型 Top-K 必须在 1 到 1000 之间");
        }
        if (request.getMaxTokens() != null && (request.getMaxTokens() < 1 || request.getMaxTokens() > 1_000_000)) {
            throw ApiException.badRequest("INVALID_MAX_TOKENS", "Max Tokens 必须在 1 到 1000000 之间");
        }
        if (request.getFrequencyPenalty() != null && (request.getFrequencyPenalty() < -2 || request.getFrequencyPenalty() > 2)) {
            throw ApiException.badRequest("INVALID_FREQUENCY_PENALTY", "频率惩罚必须在 -2 到 2 之间");
        }
        if (request.getReasoningEffort() != null && !List.of("none", "low", "medium", "high").contains(request.getReasoningEffort())) {
            throw ApiException.badRequest("INVALID_REASONING_EFFORT", "推理强度只能是 none、low、medium 或 high");
        }
        if (request.getStrategy() != null && !List.of("AUTO", "DIRECT", "REACT", "PLAN_AND_SOLVE", "REFLECTION").contains(request.getStrategy().toUpperCase(Locale.ROOT))) {
            throw ApiException.badRequest("INVALID_AGENT_STRATEGY", "回答方式不受支持");
        }
    }

    private void publishStep(AgentRun run, String kind, String title, String detail, String status) throws IOException {
        publishStep(run, kind, title, detail, status, Map.of());
    }

    private void publishStep(AgentRun run, String kind, String title, String detail, String status, Map<String, Object> metadata) throws IOException {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("id", run.getRunKey() + "-" + kind);
        event.put("kind", kind);
        event.put("title", title);
        event.put("detail", detail);
        event.put("status", status);
        Map<String, Object> meta = new LinkedHashMap<>();
        meta.putAll(metadata);
        meta.remove("node");
        meta.remove("title");
        meta.remove("detail");
        if (!meta.isEmpty()) event.put("meta", meta);
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
        citation.put("content", value(item, "content", ""));
        citation.put("sourceType", value(item, "sourceType", value(item, "source_type", "internal")));
        citation.put("assetId", value(item, "assetId", value(item, "asset_id", null)));
        citation.put("chunkId", value(item, "chunkId", value(item, "chunk_id", null)));
        citation.put("score", value(item, "score", null));
        citation.put("pageNumber", page);
        citation.put("url", item.get("url"));
        citation.put("contentKind", valueAny(item, "contentKind", "content_kind", null));
        publish(run, "citation.added", Map.of("type", "citation.added", "runId", run.getRunKey(), "citation", citation));
    }

    @SuppressWarnings("unchecked")
    private void publishArtifact(AgentRun run, Map<String, Object> body, Map<String, Object> payload) throws IOException {
        if (!(payload.get("artifact") instanceof Map<?, ?> raw)) return;
        Long workspaceId = longValue(body.get("workspaceId"));
        Long projectId = longValue(body.get("projectId"));
        Long userId = longValue(body.get("userId"));
        String storageKey = String.valueOf(value(raw, "storageKey", ""));
        String expectedPrefix = "workspaces/" + workspaceId + "/projects/" + projectId + "/agent/" + run.getRunKey() + "/artifacts/";
        if (workspaceId == null || projectId == null || userId == null || !storageKey.startsWith(expectedPrefix)) {
            throw new IOException("生成文件存储路径无效");
        }
        String fileName = safeFileName(String.valueOf(valueAny(raw, "fileName", "file_name", "generated-file")));
        String mimeType = String.valueOf(valueAny(raw, "mimeType", "mime_type", "application/octet-stream"));
        long fileSize = Math.max(0L, longValue(valueAny(raw, "fileSize", "file_size", 0L)) == null ? 0L : longValue(valueAny(raw, "fileSize", "file_size", 0L)));
        if (fileSize > MAX_ATTACHMENT_BYTES) throw new IOException("生成文件超过大小限制");
        AgentAttachment attachment = mapper.findAttachmentByStorageKey(storageKey, workspaceId, projectId, userId);
        if (attachment == null) {
            attachment = new AgentAttachment();
            attachment.setWorkspaceId(workspaceId);
            attachment.setProjectId(projectId);
            attachment.setUploadedBy(userId);
            attachment.setFileName(fileName);
            attachment.setKind(kindOf(mimeType, fileName));
            attachment.setMimeType(mimeType);
            attachment.setFileSize(fileSize);
            attachment.setStorageKey(storageKey);
            mapper.insertAttachment(attachment);
        }
        Map<String, Object> attachmentMap = new LinkedHashMap<>();
        attachmentMap.put("id", String.valueOf(attachment.getId()));
        attachmentMap.put("uploadId", attachment.getId());
        attachmentMap.put("name", attachment.getFileName());
        attachmentMap.put("kind", attachment.getKind());
        attachmentMap.put("mimeType", attachment.getMimeType());
        attachmentMap.put("size", formatFileSize(attachment.getFileSize()));
        attachmentMap.put("url", "/api/workspaces/" + workspaceId + "/projects/" + projectId + "/agent/attachments/" + attachment.getId() + "/content");
        attachmentMap.put("generated", true);
        appendMessageAttachment(run.getAssistantMessageId(), attachmentMap);
        String messageId = String.valueOf(value(payload, "messageId", findMessageKey(run.getAssistantMessageId())));
        publish(run, "artifact.added", Map.of(
                "type", "artifact.added",
                "runId", run.getRunKey(),
                "messageId", messageId,
                "artifact", attachmentMap
        ));
    }

    @SuppressWarnings("unchecked")
    private void appendMessageAttachment(Long messageId, Map<String, Object> attachment) throws IOException {
        List<Map<String, Object>> attachments = new java.util.ArrayList<>();
        String current = mapper.findMessageAttachments(messageId);
        if (current != null && !current.isBlank()) {
            try {
                List<?> parsed = objectMapper.readValue(current, List.class);
                for (Object item : parsed) if (item instanceof Map<?, ?> value) attachments.add(new LinkedHashMap<>((Map<String, Object>) value));
            } catch (RuntimeException exception) {
                throw new IOException("消息附件格式无效", exception);
            }
        }
        String attachmentId = String.valueOf(attachment.get("id"));
        boolean exists = attachments.stream().anyMatch(item -> attachmentId.equals(String.valueOf(item.get("id"))));
        if (!exists) attachments.add(attachment);
        try {
            mapper.updateMessageAttachments(messageId, objectMapper.writeValueAsString(attachments));
        } catch (RuntimeException exception) {
            throw new IOException("消息附件保存失败", exception);
        }
    }

    @SuppressWarnings("unchecked")
    private void saveTokenUsage(AgentRun run, Map<String, Object> body, Map<String, Object> payload) {
        Object rawUsage = payload.get("usage");
        if (!(rawUsage instanceof Map<?, ?> usage)) return;
        Object rawCompression = payload.get("contextCompression");
        Map<?, ?> compression = rawCompression instanceof Map<?, ?> value ? value : Map.of();
        AgentTokenUsage record = new AgentTokenUsage();
        record.setWorkspaceId(longValue(body.get("workspaceId")));
        record.setProjectId(longValue(body.get("projectId")));
        record.setUserId(longValue(body.get("userId")));
        record.setRunId(run.getId());
        record.setRunKey(run.getRunKey());
        Object model = firstValue(usage, "model", "modelName", "model_name");
        if (model == null) model = firstValue(payload, "model", "modelName", "model_name");
        if (model != null && !String.valueOf(model).isBlank()) record.setModelName(String.valueOf(model));
        record.setInputTokens(intValue(firstValue(usage, "inputTokens", "input_tokens", "promptTokens", "prompt_tokens"), null));
        record.setOutputTokens(intValue(firstValue(usage, "outputTokens", "output_tokens", "completionTokens", "completion_tokens"), null));
        record.setTotalTokens(intValue(firstValue(usage, "totalTokens", "total_tokens"), null));
        if (record.getTotalTokens() == 0) record.setTotalTokens(record.getInputTokens() + record.getOutputTokens());
        int originalContextTokens = intValue(firstValue(compression, "originalTokenEstimate", "original_token_estimate"), null);
        int finalContextTokens = intValue(firstValue(compression, "finalTokenEstimate", "final_token_estimate"), null);
        record.setCompressedContextTokens(Math.max(0, originalContextTokens - finalContextTokens));
        record.setContextMessageCount(intValue(firstValue(compression, "finalMessageCount", "final_message_count"), null));
        mapper.upsertTokenUsage(record);
    }

    private Map<String, Object> normalizeTokenUsage(Map<?, ?> raw) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        putNormalized(normalized, "inputTokens", raw, "inputTokens", "input_tokens", "promptTokens", "prompt_tokens");
        putNormalized(normalized, "outputTokens", raw, "outputTokens", "output_tokens", "completionTokens", "completion_tokens");
        putNormalized(normalized, "totalTokens", raw, "totalTokens", "total_tokens");
        putNormalized(normalized, "model", raw, "model", "modelName", "model_name");
        putNormalized(normalized, "available", raw, "available");
        putNormalized(normalized, "estimated", raw, "estimated");
        return normalized.isEmpty() ? null : normalized;
    }

    private Map<String, Object> normalizeContextUsage(Map<?, ?> raw) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        putNormalized(normalized, "originalChars", raw, "originalChars", "original_chars");
        putNormalized(normalized, "finalChars", raw, "finalChars", "final_chars");
        putNormalized(normalized, "compressedMessages", raw, "compressedMessages", "compressed_messages");
        putNormalized(normalized, "originalTokenEstimate", raw, "originalTokenEstimate", "original_token_estimate");
        putNormalized(normalized, "finalTokenEstimate", raw, "finalTokenEstimate", "final_token_estimate");
        putNormalized(normalized, "finalMessageCount", raw, "finalMessageCount", "final_message_count");
        putNormalized(normalized, "compressedContextTokens", raw, "compressedContextTokens", "compressed_context_tokens");
        putNormalized(normalized, "modelContextWindow", raw, "modelContextWindow", "model_context_window");
        putNormalized(normalized, "contextTokenBudget", raw, "contextTokenBudget", "context_token_budget");
        putNormalized(normalized, "compressionTriggered", raw, "compressionTriggered", "compression_triggered");
        return normalized.isEmpty() ? null : normalized;
    }

    private void putNormalized(Map<String, Object> target, String targetKey, Map<?, ?> source, String... sourceKeys) {
        Object value = firstValue(source, sourceKeys);
        if (value != null) target.put(targetKey, value);
    }

    private boolean hasStoredTokenUsage(AgentTokenUsage usage) {
        return (usage.getInputTokens() != null && usage.getInputTokens() > 0)
                || (usage.getOutputTokens() != null && usage.getOutputTokens() > 0)
                || (usage.getTotalTokens() != null && usage.getTotalTokens() > 0);
    }

    private Object firstValue(Map<?, ?> source, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value != null) return value;
        }
        return null;
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

    private Integer intValue(Object first, Object fallback) {
        Object value = first == null ? fallback : first;
        if (value == null) return 0;
        try { return Integer.valueOf(String.valueOf(value)); } catch (NumberFormatException ignored) { return 0; }
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
            payload.putIfAbsent("eventId", String.valueOf(event.getId()));
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
        return "COMPLETED".equals(status) || "FAILED".equals(status) || "CANCELLED".equals(status);
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

    private String summarizeThreadTitle(String value) {
        String text = value == null ? "" : value.replaceAll("\\s+", " ").trim();
        text = text.replaceFirst("^(请问|请帮我|帮我|我想|想了解|能否|可以)\\s*", "");
        text = text.replaceAll("[。！？?!；;：:]+$", "").trim();
        if (text.isBlank()) return "新的问题整理";
        String summary;
        if (text.matches("^为什么\\s*.+")) summary = "排查" + text.substring(3).trim() + "问题";
        else if (text.matches("^(如何|怎么|怎样)\\s*.+")) summary = "梳理" + text.replaceFirst("^(如何|怎么|怎样)\\s*", "") + "方案";
        else if (text.matches("^(什么是|是什么)\\s*.+")) summary = "了解" + text.replaceFirst("^(什么是|是什么)\\s*", "");
        else if (text.matches("^(总结|概括)\\s*.+")) summary = "总结" + text.replaceFirst("^(总结|概括)\\s*", "");
        else if (text.matches("^(比较|对比)\\s*.+")) summary = "比较" + text.replaceFirst("^(比较|对比)\\s*", "");
        else summary = "整理：" + text;
        return shortText(summary, 80);
    }

    private String quote(String value) {
        String cleaned = value == null ? "" : value.replaceAll("\\s+", " ").trim();
        return shortText(cleaned, 260);
    }

    private String formatFileSize(Long bytes) {
        long value = bytes == null ? 0L : Math.max(0L, bytes);
        if (value < 1024) return value + " B";
        if (value < 1024 * 1024) return String.format(Locale.ROOT, "%.1f KB", value / 1024.0);
        return String.format(Locale.ROOT, "%.1f MB", value / (1024.0 * 1024.0));
    }

    private String kindOf(String mimeType, String fileName) {
        String mime = mimeType == null ? "" : mimeType.toLowerCase(Locale.ROOT);
        String extension = extension(fileName);
        if (mime.startsWith("image/")) return "image";
        if (mime.startsWith("video/")) return "video";
        if (mime.startsWith("audio/")) return "audio";
        if (mime.contains("pdf") || extension.equals("pdf")) return "pdf";
        if (Set.of("doc", "docx", "odt", "rtf", "md", "markdown", "txt").contains(extension)) return "document";
        if (Set.of("xls", "xlsx", "ods", "csv").contains(extension)) return "spreadsheet";
        if (Set.of("ppt", "pptx", "odp").contains(extension)) return "presentation";
        return "file";
    }

    private List<Map<String, Object>> attachmentPayload(Long workspaceId, Long projectId, Long userId, List<Map<String, Object>> references) {
        if (references == null || references.isEmpty()) return List.of();
        List<Map<String, Object>> payload = new java.util.ArrayList<>();
        for (Map<String, Object> reference : references) {
            Long attachmentId = longValue(reference == null ? null : reference.get("uploadId"));
            if (attachmentId == null) continue;
            AgentAttachment attachment = mapper.findAttachment(attachmentId, workspaceId, projectId, userId);
            if (attachment == null || attachment.getStorageKey() == null || attachment.getStorageKey().isBlank()) continue;
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("attachmentId", attachment.getId());
            item.put("fileName", attachment.getFileName());
            item.put("mimeType", attachment.getMimeType());
            item.put("storageKey", attachment.getStorageKey());
            item.put("fileSize", attachment.getFileSize());
            payload.add(item);
        }
        return payload;
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
