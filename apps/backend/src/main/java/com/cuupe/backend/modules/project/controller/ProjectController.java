package com.cuupe.backend.modules.project.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.dto.ProjectRequest;
import com.cuupe.backend.modules.project.entity.Project;
import com.cuupe.backend.modules.project.service.ProjectService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects")
@RequiredArgsConstructor
public class ProjectController {
    private final ProjectService projectService;
    private final AuditLogService auditLogService;

    @GetMapping
    public Result<List<Project>> list(@PathVariable Long workspaceId, Authentication authentication) {
        return Result.success(projectService.list(workspaceId, userId(authentication)));
    }

    @PostMapping
    public Result<Project> create(@PathVariable Long workspaceId, @Valid @RequestBody ProjectRequest request, Authentication authentication) {
        Long userId = userId(authentication);
        Project project = projectService.create(workspaceId, userId, request);
        auditLogService.record(workspaceId, project.getId(), userId, "PROJECT_CREATED", "PROJECT", project.getId(), Map.of("name", project.getName()));
        return Result.success(project);
    }

    @GetMapping("/{projectId}")
    public Result<Project> detail(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication authentication) {
        return Result.success(projectService.detail(workspaceId, projectId, userId(authentication)));
    }

    @PatchMapping("/{projectId}")
    public Result<Project> update(@PathVariable Long workspaceId, @PathVariable Long projectId, @Valid @RequestBody ProjectRequest request, Authentication authentication) {
        Long userId = userId(authentication);
        Project project = projectService.update(workspaceId, projectId, userId, request);
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_UPDATED", "PROJECT", projectId, Map.of("name", project.getName()));
        return Result.success(project);
    }

    @DeleteMapping("/{projectId}")
    public Result<Void> delete(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication authentication) {
        Long userId = userId(authentication);
        projectService.delete(workspaceId, projectId, userId);
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_DELETED", "PROJECT", projectId);
        return Result.success();
    }

    @PatchMapping("/{projectId}/archive")
    public Result<Project> archive(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication authentication) {
        Long userId = userId(authentication);
        Project project = projectService.changeStatus(workspaceId, projectId, userId, "ARCHIVED");
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_ARCHIVED", "PROJECT", projectId);
        return Result.success(project);
    }

    @PatchMapping("/{projectId}/restore")
    public Result<Project> restore(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication authentication) {
        Long userId = userId(authentication);
        Project project = projectService.changeStatus(workspaceId, projectId, userId, "ACTIVE");
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_RESTORED", "PROJECT", projectId);
        return Result.success(project);
    }

    private Long userId(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (!(principal instanceof UserLoginByPassword user) || user.getId() == null) throw new IllegalStateException("当前会话缺少用户信息");
        return user.getId();
    }
}
