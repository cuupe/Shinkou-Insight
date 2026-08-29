package com.cuupe.backend.modules.statistics.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.statistics.dto.StatisticsResponse;
import com.cuupe.backend.modules.statistics.mapper.StatisticsMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/workspaces")
@RequiredArgsConstructor
public class StatisticsController {
    private final StatisticsMapper statisticsMapper;
    private final WorkspaceMapper workspaceMapper;
    private final ProjectMapper projectMapper;

    @GetMapping("/{workspaceId}/statistics")
    public Result<StatisticsResponse> workspace(@PathVariable Long workspaceId,
                                                @RequestParam(defaultValue = "30") int days,
                                                Authentication authentication) {
        Long userId = userId(authentication);
        if (workspaceMapper.findAccessible(workspaceId, userId) == null) throw notFound("工作区不存在或无权访问");
        return Result.success(load(workspaceId, null, userId, days));
    }

    @GetMapping("/{workspaceId}/projects/{projectId}/statistics")
    public Result<StatisticsResponse> project(@PathVariable Long workspaceId,
                                              @PathVariable Long projectId,
                                              @RequestParam(defaultValue = "30") int days,
                                              Authentication authentication) {
        Long userId = userId(authentication);
        if (projectMapper.findAccessibleById(workspaceId, projectId, userId) == null) throw notFound("项目不存在或无权访问");
        return Result.success(load(workspaceId, projectId, userId, days));
    }

    private StatisticsResponse load(Long workspaceId, Long projectId, Long userId, int days) {
        int normalizedDays = Math.max(7, Math.min(days, 90));
        StatisticsResponse response = new StatisticsResponse();
        response.setSummary(statisticsMapper.findSummary(workspaceId, projectId, userId));
        response.setDailyTrend(statisticsMapper.findDailyTrend(workspaceId, projectId, userId, normalizedDays));
        response.setRunStatuses(statisticsMapper.findRunStatuses(workspaceId, projectId, userId));
        response.setAssetStatuses(statisticsMapper.findAssetStatuses(workspaceId, projectId, userId));
        response.setActionItemStatuses(statisticsMapper.findActionItemStatuses(workspaceId, projectId, userId));
        return response;
    }

    private Long userId(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (!(principal instanceof UserLoginByPassword user) || user.getId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "当前会话无效");
        }
        return user.getId();
    }

    private ApiException notFound(String message) {
        return new ApiException(HttpStatus.NOT_FOUND, "STATISTICS_SCOPE_NOT_FOUND", message);
    }
}
