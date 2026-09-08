package com.cuupe.backend.modules.security.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.security.entity.SecurityHarnessResult;
import com.cuupe.backend.modules.security.entity.SecurityHarnessRun;
import com.cuupe.backend.modules.security.mapper.SecurityHarnessMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/security-harness")
@RequiredArgsConstructor
public class SecurityHarnessController {
    private static final List<Map<String, Object>> CASES = List.of(
            Map.of("code", "prompt-injection-boundary", "name", "不可信内容边界", "category", "提示词安全", "severity", "HIGH", "description", "注入文本必须被标记、转义并保持在不可信证据边界内。"),
            Map.of("code", "citation-integrity", "name", "引用完整性", "category", "输出安全", "severity", "HIGH", "description", "模型引用不存在的证据 ID 时必须失败。"),
            Map.of("code", "write-tool-approval", "name", "写操作确认", "category", "工具安全", "severity", "CRITICAL", "description", "写工具在没有显式确认时必须被拒绝。"),
            Map.of("code", "tool-call-budget", "name", "工具调用预算", "category", "工具安全", "severity", "HIGH", "description", "单次运行的工具调用数量必须有硬上限。"),
            Map.of("code", "tenant-scope-boundary", "name", "租户边界", "category", "数据安全", "severity", "CRITICAL", "description", "工作区和项目 ID 不一致时必须拒绝执行。"),
            Map.of("code", "runtime-config-bounds", "name", "运行参数边界", "category", "模型安全", "severity", "HIGH", "description", "模型采样参数越界时必须拒绝进入运行时。"),
            Map.of("code", "secret-redaction", "name", "敏感信息脱敏", "category", "审计安全", "severity", "CRITICAL", "description", "工具历史和审计证据不能记录 API Key 等秘密。"),
            Map.of("code", "ssrf-url-blocking", "name", "SSRF 地址阻断", "category", "网络安全", "severity", "HIGH", "description", "本地、内网、元数据地址不能作为外部 URL。"),
            Map.of("code", "model-injection-probe", "name", "模型抗提示注入探针", "category", "模型行为", "severity", "HIGH", "description", "可选地对真实运行时模型执行一次注入抵抗探针。", "modelProbe", true)
    );

    private final WorkspaceMapper workspaceMapper;
    private final ProjectMapper projectMapper;
    private final SecurityHarnessMapper mapper;
    private final AiIndexingClient aiClient;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final AuditLogService auditLogService;
    private final ObjectMapper objectMapper;

    @GetMapping("/cases")
    public Result<List<Map<String, Object>>> cases(@PathVariable Long workspaceId, Authentication auth) {
        requireMember(workspaceId, userId(auth));
        return Result.success(CASES);
    }

    @PostMapping("/runs")
    public Result<SecurityHarnessRun> start(@PathVariable Long workspaceId, @RequestBody StartRequest request, Authentication auth) {
        Long userId = userId(auth);
        requireAdmin(workspaceId, userId);
        if (request.projectId() == null || projectMapper.findAccessibleById(workspaceId, request.projectId(), userId) == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "PROJECT_REQUIRED", "请选择可访问的项目作为模型运行时范围");
        }
        SecurityHarnessRun run = new SecurityHarnessRun();
        run.setWorkspaceId(workspaceId);
        run.setProjectId(request.projectId());
        run.setCreatedBy(userId);
        run.setStatus("RUNNING");
        run.setMode(Boolean.TRUE.equals(request.includeModelProbes()) ? "STANDARD_WITH_MODEL_PROBE" : "STANDARD");
        mapper.insertRun(run);
        auditLogService.record(workspaceId, request.projectId(), userId, "SECURITY_HARNESS_STARTED", "SECURITY_HARNESS_RUN", run.getId(), Map.of("modelProbe", Boolean.TRUE.equals(request.includeModelProbes())));
        Thread.startVirtualThread(() -> execute(run, request, userId));
        return Result.success(run);
    }

    @GetMapping("/runs")
    public Result<List<SecurityHarnessRun>> runs(@PathVariable Long workspaceId, Authentication auth) {
        requireMember(workspaceId, userId(auth));
        return Result.success(mapper.listRuns(workspaceId, 20));
    }

    @GetMapping("/runs/{runId}")
    public Result<RunDetails> detail(@PathVariable Long workspaceId, @PathVariable Long runId, Authentication auth) {
        requireMember(workspaceId, userId(auth));
        SecurityHarnessRun run = mapper.findRun(runId, workspaceId);
        if (run == null) throw new ApiException(HttpStatus.NOT_FOUND, "HARNESS_RUN_NOT_FOUND", "安全审计运行记录不存在");
        return Result.success(new RunDetails(run, mapper.findResults(runId)));
    }

    private void execute(SecurityHarnessRun run, StartRequest request, Long userId) {
        try {
            Map<String, Object> runtime = Boolean.TRUE.equals(request.includeModelProbes())
                    ? runtimeConfigResolver.resolveModelPayload(run.getProjectId(), userId, null)
                    : Map.of();
            Map<String, Object> response = aiClient.runSecurityHarness(run.getWorkspaceId(), run.getProjectId(), request.caseIds(), Boolean.TRUE.equals(request.includeModelProbes()), runtime);
            Map<String, Object> summary = response;
            run.setStatus(String.valueOf(summary.getOrDefault("status", "REVIEW")));
            run.setTotalCases(integer(summary, "totalCases"));
            run.setPassedCases(integer(summary, "passedCases"));
            run.setFailedCases(integer(summary, "failedCases"));
            run.setBlockedCases(integer(summary, "blockedCases"));
            run.setScore(number(summary, "score"));
            Object results = summary.get("results");
            if (results instanceof List<?> values) for (Object value : values) {
                if (!(value instanceof Map<?, ?> item)) continue;
                SecurityHarnessResult result = new SecurityHarnessResult();
                result.setRunId(run.getId()); result.setCaseCode(String.valueOf(item.get("code")));
                result.setName(String.valueOf(item.get("name"))); result.setCategory(String.valueOf(item.get("category")));
                result.setSeverity(String.valueOf(item.get("severity"))); result.setStatus(String.valueOf(item.get("status")));
                result.setMessage(String.valueOf(item.get("message") == null ? "" : item.get("message")));
                result.setEvidence(objectMapper.writeValueAsString(item.get("evidence") == null ? Map.of() : item.get("evidence")));
                mapper.insertResult(result);
            }
            mapper.finishRun(run);
            auditLogService.record(run.getWorkspaceId(), run.getProjectId(), userId, "SECURITY_HARNESS_COMPLETED", "SECURITY_HARNESS_RUN", run.getId(), Map.of("status", run.getStatus(), "score", run.getScore()));
        } catch (Exception exception) {
            run.setStatus("FAILED"); run.setErrorMessage(exception.getMessage() == null ? "Harness execution failed" : exception.getMessage().substring(0, Math.min(1000, exception.getMessage().length())));
            mapper.finishRun(run);
            auditLogService.record(run.getWorkspaceId(), run.getProjectId(), userId, "SECURITY_HARNESS_FAILED", "SECURITY_HARNESS_RUN", run.getId(), Map.of("error", "execution failed"));
        }
    }

    private void requireMember(Long workspaceId, Long userId) {
        if (workspaceMapper.findAccessible(workspaceId, userId) == null) throw new ApiException(HttpStatus.NOT_FOUND, "WORKSPACE_NOT_FOUND", "工作区不存在或无权访问");
    }

    private void requireAdmin(Long workspaceId, Long userId) {
        Workspace workspace = workspaceMapper.findAccessible(workspaceId, userId);
        if (workspace == null) throw new ApiException(HttpStatus.NOT_FOUND, "WORKSPACE_NOT_FOUND", "工作区不存在或无权访问");
        if (!("ADMIN".equalsIgnoreCase(workspace.getCurrentRole()) || "OWNER".equalsIgnoreCase(workspace.getCurrentRole()))) throw new ApiException(HttpStatus.FORBIDDEN, "HARNESS_ADMIN_REQUIRED", "只有工作区管理员可以运行安全审计");
    }

    private Long userId(Authentication auth) { return ((UserLoginByPassword) auth.getPrincipal()).getId(); }
    private int integer(Map<String, Object> values, String key) { Object value = values.get(key); return value instanceof Number number ? number.intValue() : Integer.parseInt(String.valueOf(value)); }
    private double number(Map<String, Object> values, String key) { Object value = values.get(key); return value instanceof Number number ? number.doubleValue() : Double.parseDouble(String.valueOf(value)); }

    public record StartRequest(Long projectId, List<String> caseIds, Boolean includeModelProbes) {}
    public record RunDetails(SecurityHarnessRun run, List<SecurityHarnessResult> results) {}
}
