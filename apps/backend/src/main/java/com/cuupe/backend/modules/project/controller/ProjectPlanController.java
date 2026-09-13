package com.cuupe.backend.modules.project.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.dto.ProjectPlanRequest;
import com.cuupe.backend.modules.project.entity.Project;
import com.cuupe.backend.modules.project.entity.ProjectPlan;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.mapper.ProjectPlanMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/planning")
@RequiredArgsConstructor
public class ProjectPlanController {
    private final ProjectMapper projectMapper;
    private final ProjectPlanMapper planMapper;
    private final AuditLogService auditLogService;

    @GetMapping
    public Result<ProjectPlan> detail(@PathVariable Long workspaceId,
                                      @PathVariable Long projectId,
                                      Authentication authentication) {
        Long userId = userId(authentication);
        requiredProject(workspaceId, projectId, userId);
        ProjectPlan plan = planMapper.findByProject(workspaceId, projectId);
        if (plan == null) {
            plan = new ProjectPlan();
            plan.setProjectId(projectId);
            plan.setWorkspaceId(workspaceId);
            plan.setObjective("");
        }
        return Result.success(plan);
    }

    @PutMapping
    public Result<ProjectPlan> save(@PathVariable Long workspaceId,
                                    @PathVariable Long projectId,
                                    @Valid @RequestBody ProjectPlanRequest request,
                                    Authentication authentication) {
        Long userId = userId(authentication);
        requiredProject(workspaceId, projectId, userId);
        if (!projectMapper.hasWriteAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_PLAN_FORBIDDEN", "只有项目创建者或管理员可以保存规划");
        }

        ProjectPlan plan = new ProjectPlan();
        plan.setProjectId(projectId);
        plan.setWorkspaceId(workspaceId);
        plan.setObjective(value(request.objective()));
        plan.setProblem(value(request.problem()));
        plan.setSuccessMetrics(value(request.successMetrics()));
        plan.setConstraints(value(request.constraints()));
        plan.setOwner(value(request.owner()));
        plan.setDeadline(request.deadline());
        plan.setUpdatedBy(userId);
        planMapper.upsert(plan);
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_PLAN_UPDATED", "PROJECT_PLAN", projectId,
                Map.of("hasObjective", !plan.getObjective().isBlank(), "hasDeadline", plan.getDeadline() != null));
        return Result.success(planMapper.findByProject(workspaceId, projectId));
    }

    private Project requiredProject(Long workspaceId, Long projectId, Long userId) {
        Project project = projectMapper.findAccessibleById(workspaceId, projectId, userId);
        if (project == null) throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        return project;
    }

    private Long userId(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }

    private String value(String value) { return value == null ? "" : value.trim(); }
}
