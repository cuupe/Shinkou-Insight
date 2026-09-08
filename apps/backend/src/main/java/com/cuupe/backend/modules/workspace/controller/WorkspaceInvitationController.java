package com.cuupe.backend.modules.workspace.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.entity.WorkspaceInvitation;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMemberMapper;
import lombok.RequiredArgsConstructor;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;

@RestController
@RequiredArgsConstructor
public class WorkspaceInvitationController {
    private final WorkspaceMemberMapper mapper;
    private final AuditLogService auditLogService;

    @PostMapping("/workspaces/{workspaceId}/invitations")
    public Result<Map<String, String>> create(@PathVariable Long workspaceId, @RequestBody InviteRequest request, Authentication auth) throws Exception {
        if (request.phoneNumber() == null || !request.phoneNumber().matches("^1\\d{10}$"))
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_PHONE", "手机号格式不正确");
        if (!List.of("ADMIN", "MEMBER").contains(request.role()))
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_ROLE", "邀请角色不正确");
        String token = UUID.randomUUID().toString();
        Long userId = userId(auth);
        if (mapper.insertInvitation(workspaceId, request.phoneNumber(), request.department(), request.title(), request.inviteNote(), request.role(), hash(token), userId) == 0)
            throw new ApiException(HttpStatus.FORBIDDEN, "MEMBER_WRITE_FORBIDDEN", "没有邀请成员的权限");
        auditLogService.record(workspaceId, null, userId, "MEMBER_INVITED", "WORKSPACE_INVITATION", null, Map.of("phoneNumber", request.phoneNumber(), "role", request.role()));
        return Result.success(Map.of("status", "PENDING"));
    }

    @GetMapping("/workspace-invitations/me")
    public Result<List<WorkspaceInvitation>> mine(Authentication auth) {
        return Result.success(mapper.findPendingInvitations(phone(auth)));
    }

    @PostMapping("/workspace-invitations/{id}/accept")
    @Transactional
    public Result<Map<String, Object>> accept(@PathVariable Long id, Authentication auth) {
        WorkspaceInvitation invitation = mapper.findPendingInvitation(id, phone(auth));
        if (invitation == null) throw invalidInvitation();
        if (mapper.acceptInvitation(id, phone(auth), userId(auth)) == 0) throw invalidInvitation();
        auditLogService.record(invitation.getWorkspaceId(), null, userId(auth), "INVITATION_ACCEPTED", "WORKSPACE_INVITATION", id);
        return Result.success(Map.of("workspaceId", invitation.getWorkspaceId(), "status", "ACCEPTED"));
    }

    @PostMapping("/workspace-invitations/{id}/decline")
    public Result<Void> decline(@PathVariable Long id, Authentication auth) {
        if (mapper.declineInvitation(id, phone(auth)) == 0) throw invalidInvitation();
        auditLogService.record(null, null, userId(auth), "INVITATION_DECLINED", "WORKSPACE_INVITATION", id);
        return Result.success();
    }

    @DeleteMapping("/workspaces/{workspaceId}/invitations/{invitationId}")
    public Result<Void> revoke(@PathVariable Long workspaceId, @PathVariable Long invitationId, Authentication auth) {
        Long userId = userId(auth);
        if (mapper.revokeInvitation(workspaceId, invitationId, userId) == 0)
            throw new ApiException(HttpStatus.FORBIDDEN, "INVITATION_REVOKE_FORBIDDEN", "无法撤销该邀请");
        auditLogService.record(workspaceId, null, userId, "INVITATION_REVOKED", "WORKSPACE_INVITATION", invitationId);
        return Result.success();
    }

    private ApiException invalidInvitation() {
        return new ApiException(HttpStatus.NOT_FOUND, "INVITATION_NOT_FOUND", "邀请不存在、已处理或已过期");
    }
    private Long userId(Authentication auth) { return ((UserLoginByPassword) auth.getPrincipal()).getId(); }
    private String phone(Authentication auth) { return ((UserLoginByPassword) auth.getPrincipal()).getPhoneNumber(); }
    private String hash(String value) throws Exception {
        return Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
    }
    public record InviteRequest(@NotBlank String phoneNumber, @NotBlank String role, String department, String title, String inviteNote) {}
}
