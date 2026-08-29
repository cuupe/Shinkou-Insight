package com.cuupe.backend.modules.actionitem.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.actionitem.entity.ActionItem;
import com.cuupe.backend.modules.actionitem.mapper.ActionItemMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/action-items")
@RequiredArgsConstructor
public class ActionItemController {
    private final ActionItemMapper actionItemMapper;

    @GetMapping public Result<List<ActionItem>> list(@PathVariable Long projectId, Authentication auth) { return Result.success(actionItemMapper.findByProject(projectId, userId(auth))); }

    @PostMapping
    public Result<ActionItem> create(@PathVariable Long projectId, @RequestBody ActionItem item, Authentication auth) {
        item.setProjectId(projectId); item.setCreatedBy(userId(auth));
        if (item.getTitle() == null || item.getTitle().isBlank()) throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "行动项标题不能为空");
        item.setPriority(normalizePriority(item.getPriority() == null ? "MEDIUM" : item.getPriority()));
        item.setStatus(normalizeStatus(item.getStatus() == null ? "DRAFT" : item.getStatus()));
        actionItemMapper.insert(item);
        return Result.success(actionItemMapper.findById(item.getId(), projectId, userId(auth)));
    }

    @PatchMapping("/{id}")
    public Result<ActionItem> update(@PathVariable Long projectId, @PathVariable Long id, @RequestBody Map<String, Object> body, Authentication auth) {
        ActionItem item = actionItemMapper.findById(id, projectId, userId(auth));
        if (item == null) throw notFound();
        if (body.containsKey("title")) item.setTitle((String) body.get("title"));
        if (body.containsKey("description")) item.setDescription((String) body.get("description"));
        if (body.containsKey("ownerId")) item.setOwnerId(((Number) body.get("ownerId")).longValue());
        if (body.containsKey("dueAt")) item.setDueAt(body.get("dueAt") == null ? null : LocalDate.parse((String) body.get("dueAt")));
        if (body.containsKey("priority")) item.setPriority(normalizePriority((String) body.get("priority")));
        if (body.containsKey("status")) item.setStatus(normalizeStatus((String) body.get("status")));
        actionItemMapper.update(item);
        return Result.success(actionItemMapper.findById(id, projectId, userId(auth)));
    }

    private Long userId(Authentication auth) { Object principal=auth.getPrincipal(); if(principal instanceof UserLoginByPassword user && user.getId()!=null) return user.getId(); throw new IllegalStateException("当前会话缺少用户信息"); }
    private String normalizeStatus(String status) { return switch(status.toLowerCase()) { case "todo", "draft" -> "DRAFT"; case "in-progress", "in_progress", "accepted" -> "IN_PROGRESS"; case "done" -> "DONE"; case "rejected" -> "REJECTED"; default -> throw new ApiException(HttpStatus.BAD_REQUEST,"INVALID_ACTION_STATUS","行动项状态不正确"); }; }
    private String normalizePriority(String priority) { return switch(priority.toLowerCase()) { case "高", "high" -> "HIGH"; case "低", "low" -> "LOW"; case "中", "medium", "normal" -> "MEDIUM"; default -> throw new ApiException(HttpStatus.BAD_REQUEST,"INVALID_ACTION_PRIORITY","行动项优先级不正确"); }; }
    private ApiException notFound() { return new ApiException(HttpStatus.NOT_FOUND,"ACTION_ITEM_NOT_FOUND","行动项不存在或无权访问"); }
}
