package com.cuupe.backend.modules.report.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.report.entity.Report;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.http.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/reports")
@RequiredArgsConstructor
public class ReportController {
    private final ReportMapper mapper;
    private final NotificationService notificationService;
    private final AuditLogService auditLogService;

    @GetMapping
    public Result<List<Report>> list(@PathVariable Long projectId, Authentication auth) {
        return Result.success(mapper.findByProject(projectId, userId(auth)));
    }

    @GetMapping("/{reportId}")
    public Result<Report> detail(@PathVariable Long projectId, @PathVariable Long reportId, Authentication auth) {
        return Result.success(required(reportId, projectId, userId(auth)));
    }

    @PatchMapping("/{reportId}")
    public Result<Report> update(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            @PathVariable Long reportId,
            @RequestBody Map<String, Object> body,
            Authentication auth
    ) {
        Long userId = userId(auth);
        Report report = required(reportId, projectId, userId);
        if (body.containsKey("title")) report.setTitle(stringValue(body.get("title")));
        if (body.containsKey("status")) report.setStatus(stringValue(body.get("status")));
        if (body.containsKey("versionNo")) report.setVersionNo(stringValue(body.get("versionNo")));
        if (body.containsKey("lead")) report.setLead(stringValue(body.get("lead")));
        if (body.containsKey("summary")) report.setSummary(stringValue(body.get("summary")));
        if (body.containsKey("recommendation")) report.setRecommendation(stringValue(body.get("recommendation")));
        if (body.containsKey("recommendationDetail")) report.setRecommendationDetail(stringValue(body.get("recommendationDetail")));
        if (body.containsKey("citations")) report.setCitations(integerValue(body.get("citations")));
        if (body.containsKey("content")) report.setContent(stringValue(body.get("content")));
        mapper.update(report);
        auditLogService.record(workspaceId, projectId, userId, "REPORT_UPDATED", "REPORT", reportId);
        notificationService.create(workspaceId, userId, projectId, "report", "报告已更新", "“" + report.getTitle() + "”的内容已发生更新。", "project-reports");
        return Result.success(required(reportId, projectId, userId));
    }

    @GetMapping("/{reportId}/export")
    public ResponseEntity<byte[]> export(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long reportId, @RequestParam(defaultValue = "markdown") String format, Authentication auth) {
        Long userId = userId(auth);
        Report report = required(reportId, projectId, userId);
        auditLogService.record(workspaceId, projectId, userId, "REPORT_EXPORTED", "REPORT", reportId, Map.of("format", format));
        String content = report.getContent() == null ? "" : report.getContent();
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_PLAIN)
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=report-" + reportId + "." + (format.equalsIgnoreCase("json") ? "json" : "md"))
                .body(content.getBytes(StandardCharsets.UTF_8));
    }

    private String stringValue(Object value) { return value == null ? null : String.valueOf(value); }
    private Integer integerValue(Object value) { return value == null ? null : Integer.valueOf(String.valueOf(value)); }
    private Report required(Long id, Long projectId, Long userId) { Report report = mapper.findById(id, projectId, userId); if (report == null) throw new ApiException(HttpStatus.NOT_FOUND, "REPORT_NOT_FOUND", "报告不存在或无权访问"); return report; }
    private Long userId(Authentication auth) { Object principal = auth.getPrincipal(); if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId(); throw new IllegalStateException("当前会话缺少用户信息"); }
}
