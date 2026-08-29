package com.cuupe.backend.modules.workspace.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMemberMapper;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/workspaces/{workspaceId}/invitations")
@RequiredArgsConstructor
public class WorkspaceInvitationController {
    private final WorkspaceMemberMapper mapper;

    @PostMapping
    public Result<Map<String, String>> create(
            @PathVariable Long workspaceId,
            @RequestBody InviteRequest request,
            Authentication auth
    ) throws Exception {
        if (!request.phoneNumber().matches("^1\\d{10}$")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_PHONE", "手机号格式不正确");
        }
        if (!List.of("ADMIN", "MEMBER").contains(request.role())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_ROLE", "邀请角色不正确");
        }

        String token = UUID.randomUUID().toString();
        Long userId = ((UserLoginByPassword) auth.getPrincipal()).getId();
        int inserted = mapper.insertInvitation(
                workspaceId,
                request.phoneNumber(),
                request.department(),
                request.title(),
                request.inviteNote(),
                request.role(),
                hash(token),
                userId
        );
        if (inserted == 0) {
            throw new ApiException(HttpStatus.FORBIDDEN, "MEMBER_WRITE_FORBIDDEN", "没有邀请成员的权限");
        }
        return Result.success(Map.of("status", "PENDING"));
    }

    private String hash(String value) throws Exception {
        return Base64.getEncoder().encodeToString(
                MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))
        );
    }

    public record InviteRequest(
            @NotBlank String phoneNumber,
            @NotBlank String role,
            String department,
            String title,
            String inviteNote
    ) {}
}
