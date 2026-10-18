package com.cuupe.backend.modules.project.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.project.entity.ProjectReviewPolicy;
import com.cuupe.backend.modules.project.entity.ProjectReviewRun;
import com.cuupe.backend.modules.project.service.ProjectReviewService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/review")
@RequiredArgsConstructor
public class ProjectReviewController {
    private final ProjectReviewService service;

    @GetMapping("/policy")
    public Result<ProjectReviewPolicy> policy(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication authentication) {
        return Result.success(service.policy(workspaceId, projectId, userId(authentication)));
    }
    @PutMapping("/policy")
    public Result<ProjectReviewPolicy> savePolicy(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                                 @Valid @RequestBody ProjectReviewPolicy request, Authentication authentication) {
        return Result.success(service.savePolicy(workspaceId, projectId, userId(authentication), request));
    }
    @GetMapping("/latest")
    public Result<ProjectReviewRun> latest(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                           @RequestParam(required=false) Long reportId, Authentication authentication) {
        return Result.success(service.latest(workspaceId, projectId, reportId, userId(authentication)));
    }
    @GetMapping("/runs")
    public Result<List<ProjectReviewRun>> history(@PathVariable Long workspaceId, @PathVariable Long projectId, Authentication authentication) {
        return Result.success(service.history(workspaceId, projectId, userId(authentication)));
    }
    @PostMapping("/runs")
    public Result<ProjectReviewRun> run(@PathVariable Long workspaceId, @PathVariable Long projectId,
                                        @RequestBody(required=false) RunRequest request, Authentication authentication) {
        return Result.success(service.run(workspaceId, projectId, request == null ? null : request.reportId(), userId(authentication)));
    }
    @PostMapping("/runs/{id}/decision")
    public Result<ProjectReviewRun> decide(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long id,
                                           @Valid @RequestBody DecisionRequest request, Authentication authentication) {
        return Result.success(service.decide(workspaceId, projectId, id, userId(authentication), request.decision(), request.comment(), request.confirmations()));
    }
    public record RunRequest(Long reportId) {}
    public record DecisionRequest(@NotBlank String decision, @NotBlank @Size(max=4000) String comment,
                                  @Size(max=16) List<@NotBlank String> confirmations) {}
    private Long userId(Authentication authentication) {
        if (authentication.getPrincipal() instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }
}
