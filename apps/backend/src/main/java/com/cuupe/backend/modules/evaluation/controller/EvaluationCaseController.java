package com.cuupe.backend.modules.evaluation.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.evaluation.entity.EvaluationCase;
import com.cuupe.backend.modules.evaluation.mapper.EvaluationCaseMapper;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/evaluation-cases")
@RequiredArgsConstructor
public class EvaluationCaseController {
    private final EvaluationCaseMapper mapper;
    private final NotificationService notificationService;

    @GetMapping
    public Result<List<EvaluationCase>> list(
            @PathVariable Long workspaceId,
            Authentication auth
    ) {
        return Result.success(mapper.findByWorkspace(workspaceId, userId(auth)));
    }

    @PostMapping
    public Result<EvaluationCase> create(
            @PathVariable Long workspaceId,
            @Valid @RequestBody CaseRequest request,
            Authentication auth
    ) {
        EvaluationCase item = new EvaluationCase();
        item.setWorkspaceId(workspaceId);
        item.setProjectId(request.projectId());
        item.setQuery(request.query());
        item.setExpectedAnswer(request.expectedAnswer());
        item.setCreatedBy(userId(auth));
        mapper.insert(item);
        notificationService.create(
                workspaceId,
                userId(auth),
                request.projectId(),
                "evaluation",
                "评估用例已创建",
                "新的评估用例已加入评估集。",
                "project-evaluation"
        );
        return Result.success(item);
    }

    @PatchMapping("/{caseId}")
    public Result<EvaluationCase> updateStatus(
            @PathVariable Long workspaceId,
            @PathVariable Long caseId,
            @RequestBody Map<String, Object> body,
            Authentication auth
    ) {
        Long userId = userId(auth);
        String status = normalizeStatus(body.get("status"));
        if (mapper.updateStatus(workspaceId, caseId, userId, status) == 0) {
            throw new ApiException(
                    HttpStatus.NOT_FOUND,
                    "EVALUATION_CASE_NOT_FOUND",
                    "评估用例不存在或无权访问"
            );
        }
        return Result.success(mapper.findById(workspaceId, caseId, userId));
    }

    private String normalizeStatus(Object value) {
        if (value == null) {
            throw new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "INVALID_EVALUATION_STATUS",
                    "评估状态不能为空"
            );
        }
        return switch (String.valueOf(value).trim().toUpperCase()) {
            case "PASSED" -> "PASSED";
            case "REVIEW" -> "REVIEW";
            case "FAILED" -> "FAILED";
            default -> throw new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "INVALID_EVALUATION_STATUS",
                    "评估状态不正确"
            );
        };
    }

    private Long userId(Authentication auth) {
        return ((UserLoginByPassword) auth.getPrincipal()).getId();
    }

    public record CaseRequest(Long projectId, @NotBlank String query, String expectedAnswer) {
    }
}
