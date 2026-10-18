package com.cuupe.backend.modules.actionitem.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.actionitem.entity.ActionItem;
import com.cuupe.backend.modules.actionitem.service.ActionItemService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/action-items")
@RequiredArgsConstructor
public class ActionItemController {
    private final ActionItemService service;

    @GetMapping public Result<List<ActionItem>> list(@PathVariable Long workspaceId,@PathVariable Long projectId,
            @RequestParam(required=false) Long reportId,Authentication auth) {
        return Result.success(service.list(workspaceId,projectId,userId(auth),reportId));
    }
    @GetMapping("/permissions") public Result<Map<String,Boolean>> permissions(@PathVariable Long workspaceId,@PathVariable Long projectId,Authentication auth) {
        return Result.success(Map.of("canManage",service.canManage(workspaceId,projectId,userId(auth))));
    }
    @GetMapping("/report-draft/{reportId}") public Result<ActionItemService.ReportDraft> draft(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long reportId,Authentication auth) {
        return Result.success(service.draft(workspaceId,projectId,reportId,userId(auth)));
    }
    @PostMapping("/from-report/{reportId}") public Result<List<ActionItem>> importReport(@PathVariable Long workspaceId,@PathVariable Long projectId,
            @PathVariable Long reportId,@RequestBody ActionItemService.ImportRequest request,Authentication auth) {
        return Result.success(service.importReport(workspaceId,projectId,reportId,userId(auth),request));
    }

    @PostMapping
    public Result<ActionItem> create(@PathVariable Long workspaceId, @PathVariable Long projectId, @RequestBody ActionItem item, Authentication auth) {
        return Result.success(service.create(workspaceId,projectId,userId(auth),item));
    }

    @PatchMapping("/{id}")
    public Result<ActionItem> update(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long id, @RequestBody Map<String, Object> body, Authentication auth) {
        return Result.success(service.update(workspaceId,projectId,id,userId(auth),body));
    }

    @PostMapping("/{id}/submit") public Result<ActionItem> submit(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long id,
            @RequestBody Map<String,String> body,Authentication auth) {
        return Result.success(service.submit(workspaceId,projectId,id,userId(auth),body.get("completionEvidence")));
    }
    @PostMapping("/{id}/acceptance") public Result<ActionItem> accept(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long id,
            @RequestBody Map<String,String> body,Authentication auth) {
        return Result.success(service.accept(workspaceId,projectId,id,userId(auth),body.get("decision"),body.get("comment")));
    }

    private Long userId(Authentication auth) { Object principal=auth.getPrincipal(); if(principal instanceof UserLoginByPassword user && user.getId()!=null) return user.getId(); throw new IllegalStateException("当前会话缺少用户信息"); }
}
