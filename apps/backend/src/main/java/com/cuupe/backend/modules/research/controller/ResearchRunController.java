package com.cuupe.backend.modules.research.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.research.entity.ResearchRun;
import com.cuupe.backend.modules.research.mapper.ResearchRunMapper;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.ObjectMapper;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/runs")
@RequiredArgsConstructor
public class ResearchRunController {
    private final ResearchRunMapper mapper;
    private final ObjectMapper objectMapper;
    private final NotificationService notificationService;

    @GetMapping
    public Result<List<ResearchRun>> list(@PathVariable Long projectId, Authentication auth) {
        return Result.success(mapper.findByProject(projectId, userId(auth)));
    }

    @PostMapping
    public Result<ResearchRun> create(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @RequestBody Map<String, Object> body,
            Authentication auth
    ) {
        String goal = String.valueOf(body.getOrDefault("goal", "")).trim();
        if (goal.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "调研目标不能为空");
        }
        ResearchRun run = new ResearchRun();
        run.setProjectId(projectId);
        run.setCreatedBy(userId(auth));
        run.setGoal(goal);
        run.setTitle(goal.length() > 80 ? goal.substring(0, 80) : goal);
        run.setPriority(String.valueOf(body.getOrDefault("priority", "NORMAL")).toUpperCase(Locale.ROOT));
        run.setConfig(toConfig(body));
        mapper.insert(run);
        notificationService.create(
                workspaceId,
                userId(auth),
                projectId,
                "research",
                "调研运行已创建",
                "“" + run.getTitle() + "”调研任务已进入队列。",
                "project-runs"
        );
        return Result.success(mapper.findById(run.getId(), projectId, userId(auth)));
    }

    @GetMapping("/{runId}")
    public Result<ResearchRun> detail(@PathVariable Long projectId, @PathVariable Long runId, Authentication auth) {
        return Result.success(required(runId, projectId, userId(auth)));
    }

    @PostMapping("/{runId}/cancel")
    public Result<ResearchRun> cancel(@PathVariable Long projectId, @PathVariable Long runId, Authentication auth) {
        return change(runId, projectId, userId(auth), "CANCELLED");
    }

    @PostMapping("/{runId}/retry")
    public Result<ResearchRun> retry(@PathVariable Long projectId, @PathVariable Long runId, Authentication auth) {
        return change(runId, projectId, userId(auth), "PENDING");
    }

    private String toConfig(Map<String, Object> body) {
        Map<String, Object> config = new LinkedHashMap<>();
        for (String key : List.of("allowWebSearch", "maxResearchRounds", "reportTemplate", "outputLanguage")) {
            if (body.containsKey(key)) config.put(key, body.get(key));
        }
        try {
            return objectMapper.writeValueAsString(config);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_RUN_CONFIG", "调研配置格式不正确");
        }
    }

    private Result<ResearchRun> change(Long id, Long projectId, Long userId, String status) {
        required(id, projectId, userId);
        if (mapper.updateStatus(id, projectId, userId, status) == 0) throw notFound();
        return Result.success(mapper.findById(id, projectId, userId));
    }

    private ResearchRun required(Long id, Long projectId, Long userId) {
        ResearchRun run = mapper.findById(id, projectId, userId);
        if (run == null) throw notFound();
        return run;
    }

    private Long userId(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }

    private ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "RESEARCH_RUN_NOT_FOUND", "运行不存在或无权访问");
    }
}
