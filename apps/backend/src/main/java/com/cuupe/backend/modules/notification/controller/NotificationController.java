package com.cuupe.backend.modules.notification.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.notification.entity.Notification;
import com.cuupe.backend.modules.notification.mapper.NotificationMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/workspaces/{workspaceId}/notifications")
@RequiredArgsConstructor
public class NotificationController {
    private final NotificationMapper mapper;

    @GetMapping
    public Result<List<Notification>> list(
            @PathVariable Long workspaceId,
            Authentication auth
    ) {
        return Result.success(mapper.findByWorkspaceAndUser(workspaceId, userId(auth)));
    }

    @PatchMapping("/{id}/read")
    public Result<Void> markRead(
            @PathVariable Long workspaceId,
            @PathVariable Long id,
            Authentication auth
    ) {
        mapper.markRead(id, workspaceId, userId(auth));
        return Result.success();
    }

    @PatchMapping("/read-all")
    public Result<Void> markAllRead(
            @PathVariable Long workspaceId,
            Authentication auth
    ) {
        mapper.markAllRead(workspaceId, userId(auth));
        return Result.success();
    }

    private Long userId(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }
}
