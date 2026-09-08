package com.cuupe.backend.modules.audit.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.entity.AuditLog;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/workspaces/{workspaceId}/audit-logs")
@RequiredArgsConstructor
public class AuditLogController {
    private final WorkspaceMapper workspaceMapper;
    private final AuditLogService auditLogService;

    @GetMapping
    public Result<List<AuditLog>> list(@PathVariable Long workspaceId, @RequestParam(defaultValue = "50") int limit, Authentication auth) {
        Long userId = ((UserLoginByPassword) auth.getPrincipal()).getId();
        if (workspaceMapper.findAccessible(workspaceId, userId) == null) throw new ApiException(HttpStatus.NOT_FOUND, "WORKSPACE_NOT_FOUND", "工作区不存在或无权访问");
        return Result.success(auditLogService.list(workspaceId, limit));
    }
}
