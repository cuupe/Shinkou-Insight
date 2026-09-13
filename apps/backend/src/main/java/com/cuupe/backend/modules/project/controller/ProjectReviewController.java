package com.cuupe.backend.modules.project.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.entity.Project;
import com.cuupe.backend.modules.project.entity.ProjectReviewPolicy;
import com.cuupe.backend.modules.project.entity.ProjectReviewRun;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.mapper.ProjectReviewMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/review")
@RequiredArgsConstructor
public class ProjectReviewController {
    private final ProjectMapper projectMapper;
    private final ProjectReviewMapper reviewMapper;
    private final AuditLogService auditLogService;

    @GetMapping("/policy")
    public Result<ProjectReviewPolicy> policy(@PathVariable Long workspaceId,
                                              @PathVariable Long projectId,
                                              Authentication authentication) {
        requiredProject(workspaceId, projectId, userId(authentication));
        ProjectReviewPolicy policy = reviewMapper.findPolicy(workspaceId, projectId);
        return Result.success(policy == null ? defaults(workspaceId, projectId) : policy);
    }

    @PutMapping("/policy")
    public Result<ProjectReviewPolicy> savePolicy(@PathVariable Long workspaceId,
                                                  @PathVariable Long projectId,
                                                  @Valid @RequestBody ProjectReviewPolicy request,
                                                  Authentication authentication) {
        Long userId = userId(authentication);
        requiredWriteProject(workspaceId, projectId, userId);
        ProjectReviewPolicy policy = new ProjectReviewPolicy();
        policy.setProjectId(projectId);
        policy.setWorkspaceId(workspaceId);
        policy.setRequireCitations(request.isRequireCitations());
        policy.setVerifyNumbers(request.isVerifyNumbers());
        policy.setEscalateConflicts(request.isEscalateConflicts());
        policy.setLabelExternal(request.isLabelExternal());
        policy.setUpdatedBy(userId);
        reviewMapper.upsertPolicy(policy);
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_REVIEW_POLICY_UPDATED", "PROJECT_REVIEW_POLICY", projectId,
                Map.of("requireCitations", policy.isRequireCitations(), "verifyNumbers", policy.isVerifyNumbers(),
                        "escalateConflicts", policy.isEscalateConflicts(), "labelExternal", policy.isLabelExternal()));
        return Result.success(reviewMapper.findPolicy(workspaceId, projectId));
    }

    @GetMapping("/latest")
    public Result<ProjectReviewRun> latest(@PathVariable Long workspaceId,
                                           @PathVariable Long projectId,
                                           Authentication authentication) {
        requiredProject(workspaceId, projectId, userId(authentication));
        return Result.success(reviewMapper.findLatestRun(workspaceId, projectId));
    }

    @PostMapping("/runs")
    public Result<ProjectReviewRun> run(@PathVariable Long workspaceId,
                                        @PathVariable Long projectId,
                                        Authentication authentication) {
        Long userId = userId(authentication);
        requiredWriteProject(workspaceId, projectId, userId);
        ProjectReviewPolicy policy = reviewMapper.findPolicy(workspaceId, projectId);
        if (policy == null) policy = defaults(workspaceId, projectId);

        ProjectReviewRun run = new ProjectReviewRun();
        run.setProjectId(projectId);
        run.setWorkspaceId(workspaceId);
        run.setCreatedBy(userId);
        run.setAssetCount(reviewMapper.countAssets(projectId));
        run.setIndexedAssetCount(reviewMapper.countIndexedAssets(projectId));
        run.setResearchRunCount(reviewMapper.countResearchRuns(projectId));
        run.setReportCount(reviewMapper.countReports(projectId));
        run.setEvaluationCaseCount(reviewMapper.countEvaluationCases(projectId));
        run.setActionItemCount(reviewMapper.countActionItems(projectId));
        run.setRequireCitations(policy.isRequireCitations());
        run.setVerifyNumbers(policy.isVerifyNumbers());
        run.setEscalateConflicts(policy.isEscalateConflicts());
        run.setLabelExternal(policy.isLabelExternal());

        int blocked = 0;
        if (run.getIndexedAssetCount() == 0) blocked++;
        if (run.getResearchRunCount() == 0) blocked++;
        if (run.getReportCount() == 0) blocked++;
        if (run.getEvaluationCaseCount() == 0) blocked++;
        run.setBlockedCount(blocked);
        run.setReviewCount(5 - blocked);
        run.setStatus(blocked > 0 ? "BLOCKED" : "REVIEW");
        run.setDetail(blocked > 0
                ? "数据库中仍有 " + blocked + " 项发布前置条件未满足。"
                : "数据库中的资料、调研、报告和反证用例已具备，等待人工签署。 ");
        reviewMapper.insertRun(run);
        auditLogService.record(workspaceId, projectId, userId, "PROJECT_REVIEW_RUN_CREATED", "PROJECT_REVIEW_RUN", run.getId(),
                Map.of("status", run.getStatus(), "blockedCount", run.getBlockedCount()));
        return Result.success(run);
    }

    private ProjectReviewPolicy defaults(Long workspaceId, Long projectId) {
        ProjectReviewPolicy policy = new ProjectReviewPolicy();
        policy.setWorkspaceId(workspaceId);
        policy.setProjectId(projectId);
        return policy;
    }

    private void requiredWriteProject(Long workspaceId, Long projectId, Long userId) {
        requiredProject(workspaceId, projectId, userId);
        if (!projectMapper.hasWriteAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_REVIEW_FORBIDDEN", "只有项目创建者或管理员可以修改审查策略或运行审查");
        }
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
}
