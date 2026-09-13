package com.cuupe.backend.modules.agent.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.agent.dto.AgentAttachmentResponse;
import com.cuupe.backend.modules.agent.dto.AgentMessageRequest;
import com.cuupe.backend.modules.agent.dto.AgentRunAccepted;
import com.cuupe.backend.modules.agent.entity.AgentAttachment;
import com.cuupe.backend.modules.agent.service.AgentService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.List;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/agent")
@RequiredArgsConstructor
public class AgentController {
    private final AgentService agentService;
    private final AuditLogService auditLogService;

    @PostMapping("/messages")
    public Result<AgentRunAccepted> sendMessage(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @RequestBody AgentMessageRequest request,
            Authentication authentication
    ) {
        Long userId = userId(authentication);
        AgentRunAccepted accepted = agentService.accept(workspaceId, projectId, userId, request);
        auditLogService.record(workspaceId, projectId, userId, "AGENT_RUN_CREATED", "AGENT_RUN", accepted.getRunId());
        return Result.success(accepted);
    }

    @GetMapping("/threads")
    public Result<List<Map<String, Object>>> threads(
            @PathVariable Long projectId,
            Authentication authentication
    ) {
        return Result.success(agentService.history(projectId, userId(authentication)));
    }

    @DeleteMapping("/threads/{threadId}")
    public Result<Void> deleteThread(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @PathVariable String threadId,
            Authentication authentication
    ) {
        Long userId = userId(authentication);
        agentService.deleteThread(workspaceId, projectId, userId, threadId);
        auditLogService.record(workspaceId, projectId, userId, "AGENT_THREAD_DELETED", "AGENT_THREAD", threadId);
        return Result.success();
    }

    @GetMapping(value = "/runs/{runId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter events(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @PathVariable String runId,
            @RequestHeader(value = "Last-Event-ID", required = false) String lastEventId,
            Authentication authentication
    ) {
        return agentService.subscribe(workspaceId, projectId, userId(authentication), runId, parseEventId(lastEventId));
    }

    @PostMapping("/runs/{runId}/cancel")
    public Result<Void> cancel(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @PathVariable String runId,
            Authentication authentication
    ) {
        Long userId = userId(authentication);
        agentService.cancel(workspaceId, projectId, userId, runId);
        auditLogService.record(workspaceId, projectId, userId, "AGENT_RUN_CANCELLED", "AGENT_RUN", runId);
        return Result.success();
    }

    @PostMapping(value = "/attachments", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<AgentAttachmentResponse> uploadAttachment(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @RequestPart("file") MultipartFile file,
            Authentication authentication
    ) throws Exception {
        Long userId = userId(authentication);
        AgentAttachmentResponse response = agentService.uploadAttachment(workspaceId, projectId, userId, file);
        auditLogService.record(workspaceId, projectId, userId, "AGENT_ATTACHMENT_UPLOADED", "AGENT_ATTACHMENT", null, Map.of("fileName", file.getOriginalFilename() == null ? "" : file.getOriginalFilename()));
        return Result.success(response);
    }

    @GetMapping("/attachments/{attachmentId}/content")
    public ResponseEntity<byte[]> attachmentContent(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @PathVariable Long attachmentId,
            Authentication authentication
    ) {
        AgentAttachment attachment = agentService.getAttachment(workspaceId, projectId, userId(authentication), attachmentId);
        MediaType mediaType;
        try {
            mediaType = MediaType.parseMediaType(attachment.getMimeType());
        } catch (Exception ignored) {
            mediaType = MediaType.APPLICATION_OCTET_STREAM;
        }
        try (InputStream input = agentService.openAttachment(attachment)) {
            return ResponseEntity.ok()
                    .contentType(mediaType)
                    .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename*=UTF-8''" + java.net.URLEncoder.encode(attachment.getFileName(), StandardCharsets.UTF_8).replace("+", "%20"))
                    .body(input.readAllBytes());
        } catch (Exception exception) {
            throw new IllegalStateException("附件读取失败", exception);
        }
    }

    private Long userId(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }

    private Long parseEventId(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            return Long.valueOf(value);
        } catch (NumberFormatException ignored) {
            return null;
        }
    }
}
