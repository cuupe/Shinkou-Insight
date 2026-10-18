package com.cuupe.backend.modules.project.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.entity.*;
import com.cuupe.backend.modules.project.mapper.*;
import com.cuupe.backend.modules.report.entity.Report;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import com.cuupe.backend.modules.report.controller.ReportController;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import tools.jackson.databind.ObjectMapper;
import java.time.LocalDateTime;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ProjectReviewServiceTest {
    private final ProjectMapper projects = mock(ProjectMapper.class);
    private final ProjectReviewMapper reviews = mock(ProjectReviewMapper.class);
    private final ReportMapper reports = mock(ReportMapper.class);
    private final AuditLogService audit = mock(AuditLogService.class);
    private final Map<Long, ProjectReviewRun> records = new LinkedHashMap<>();
    private final ObjectMapper json = new ObjectMapper();
    private final Report report = new Report();
    private final ProjectReviewPolicy policy = new ProjectReviewPolicy();
    private ProjectReviewService service;

    @BeforeEach void setup() {
        service = new ProjectReviewService(projects, reviews, reports, audit, json);
        Project project = new Project(); project.setId(1L); project.setWorkspaceId(1L);
        when(projects.findAccessibleById(1L, 1L, 1L)).thenReturn(project);
        when(projects.hasWriteAccess(1L, 1L, 1L)).thenReturn(true);
        report.setId(100L); report.setProjectId(1L); report.setTitle("差旅制度报告"); report.setVersionNo("1");
        report.setContent("住宿标准为每晚 800 元 [E1]，适用于国内出差。"); report.setCitations(1); report.setStatus("DRAFT");
        when(reports.findById(100L, 1L, 1L)).thenReturn(report);
        when(reports.findByProject(1L, 1L)).thenReturn(List.of(report));
        when(reviews.findPolicy(1L, 1L)).thenReturn(policy);
        when(reviews.assetSnapshot(1L)).thenReturn(List.of());
        when(reviews.evaluationSnapshot(1L)).thenReturn(List.of());
        when(reviews.insertRun(any())).thenAnswer(invocation -> {
            ProjectReviewRun run = invocation.getArgument(0); run.setId((long) records.size() + 1); run.setCreatedAt(LocalDateTime.now()); records.put(run.getId(), run); return 1;
        });
        when(reviews.findRun(eq(1L), eq(1L), anyLong())).thenAnswer(invocation -> records.get(invocation.getArgument(2)));
        when(reviews.findHistory(1L, 1L)).thenAnswer(invocation -> records.values().stream().sorted(Comparator.comparing(ProjectReviewRun::getId).reversed()).toList());
        when(reviews.findLatestForReport(1L, 1L, 100L)).thenAnswer(invocation -> records.values().stream().max(Comparator.comparing(ProjectReviewRun::getId)).orElse(null));
        when(reviews.decide(any())).thenAnswer(invocation -> { ProjectReviewRun run = invocation.getArgument(0); run.setDecidedAt(LocalDateTime.now()); return 1; });
    }
    private ProjectReviewRun run() { return service.run(1L, 1L, 100L, 1L); }
    private List<String> confirmations(ProjectReviewRun run) { return run.getChecks().stream().filter(check -> check.status().equals("REVIEW")).map(ProjectReviewCheck::key).toList(); }
    private ProjectReviewRun approve(ProjectReviewRun run) { return service.decide(1L, 1L, run.getId(), 1L, "APPROVED", "已逐项核验制度原文、金额与适用条件。", confirmations(run)); }
    private void code(String expected, Runnable operation) { assertEquals(expected, assertThrows(ApiException.class, operation::run).getCode()); }

    @Test void checksAreBoundToAReportAndDoNotPretendCitationCountsProveFacts() {
        ProjectReviewRun run = run();
        assertEquals(100L, run.getReportId()); assertEquals("1", run.getReportVersion());
        assertTrue(run.getChecks().stream().anyMatch(check -> check.key().equals("citation") && check.status().equals("REVIEW")));
        assertTrue(run.getChecks().stream().anyMatch(check -> check.key().equals("numbers") && !check.excerpts().isEmpty()));
        assertEquals(0, run.getBlockedCount());
        assertEquals(run.getReviewCount(), confirmations(run).size());
    }
    @Test void absentOptionalKnowledgeAndEvaluationDoNotBlockAReport() {
        assertEquals(0, run().getBlockedCount());
    }
    @Test void missingCitationsBlockSignoff() {
        report.setContent("住宿费是每晚800元。"); report.setCitations(0);
        ProjectReviewRun run = run(); assertTrue(run.getBlockedCount() > 0);
        code("REVIEW_BLOCKED", () -> approve(run));
    }
    @Test void emptyBodyBlocksEvenWhenSummaryExists() {
        report.setContent(" "); report.setSummary("有摘要但导出正文为空");
        assertTrue(run().getChecks().stream().anyMatch(check -> check.key().equals("content") && check.status().equals("BLOCKED")));
    }
    @Test void aLinkCanSupplyACitationCandidateButRequiresHumanVerification() {
        report.setCitations(0); report.setContent("政策原文 https://example.org/policy 时间2026年，仍需确认适用范围。");
        ProjectReviewRun run = run(); assertEquals(0, run.getBlockedCount());
        assertTrue(confirmations(run).contains("external"));
    }
    @Test void noReportCreatesNoMeaninglessRun() {
        when(reports.findByProject(1L, 1L)).thenReturn(List.of());
        code("REVIEW_REPORT_REQUIRED", () -> service.run(1L, 1L, null, 1L)); verify(reviews, never()).insertRun(any());
    }
    @Test void approvalNeedsEveryHumanConfirmation() {
        ProjectReviewRun run = run();
        code("REVIEW_CONFIRMATIONS_REQUIRED", () -> service.decide(1L, 1L, run.getId(), 1L, "APPROVED", "同意", List.of()));
        verify(reviews, never()).decide(any());
    }
    @Test void approvalRequiresAMeaningfulComment() {
        ProjectReviewRun run = run();
        code("REVIEW_COMMENT_REQUIRED", () -> service.decide(1L, 1L, run.getId(), 1L, "APPROVED", " ", confirmations(run)));
        code("REVIEW_COMMENT_REQUIRED", () -> service.decide(1L, 1L, run.getId(), 1L, "CHANGES_REQUESTED", "x".repeat(4001), List.of()));
    }
    @Test void approvalIsDurableAndAllowsPublicationOfTheSameSnapshot() {
        ProjectReviewRun run = approve(run());
        assertEquals("APPROVED", run.getStatus()); assertEquals(1L, run.getDecidedBy()); assertNotNull(run.getDecidedAt());
        assertEquals(confirmations(run), run.getConfirmations());
        assertDoesNotThrow(() -> service.assertPublishable(1L, 1L, report, 1L));
        verify(audit).record(eq(1L), eq(1L), eq(1L), eq("PROJECT_REVIEW_DECIDED"), anyString(), eq(run.getId()), anyMap());
    }
    @Test void reportEditsInvalidateOldSignoffAndAreShownAsStale() {
        approve(run()); report.setContent("住宿标准改为900元 [E1]");
        assertTrue(service.history(1L, 1L, 1L).getFirst().isStale());
        assertEquals("住宿标准为每晚 800 元 [E1]，适用于国内出差。", service.history(1L, 1L, 1L).getFirst().getReportSnapshot().get("content"));
        code("REPORT_REVIEW_STALE", () -> service.assertPublishable(1L, 1L, report, 1L));
    }
    @Test void changingPolicyInvalidatesOldSignoff() {
        approve(run()); policy.setVerifyNumbers(false);
        code("REPORT_REVIEW_STALE", () -> service.assertPublishable(1L, 1L, report, 1L));
    }
    @Test void sourceIndexChangesInvalidateOldSignoff() {
        approve(run()); when(reviews.assetSnapshot(1L)).thenReturn(List.of(Map.of("id", 5, "indexStatus", "FAILED", "updatedAt", "changed")));
        code("REPORT_REVIEW_STALE", () -> service.assertPublishable(1L, 1L, report, 1L));
    }
    @Test void evaluationChangesInvalidateOldSignoff() {
        approve(run()); when(reviews.evaluationSnapshot(1L)).thenReturn(List.of(Map.of("id", 6, "retrievalStatus", "FAILED", "updatedAt", "changed")));
        code("REPORT_REVIEW_STALE", () -> service.assertPublishable(1L, 1L, report, 1L));
    }
    @Test void latestCheckSupersedesEarlierApproval() {
        approve(run()); run();
        code("REPORT_REVIEW_REQUIRED", () -> service.assertPublishable(1L, 1L, report, 1L));
    }
    @Test void anOlderUnsignedCheckCannotOverwriteTheNewerOne() {
        ProjectReviewRun old = run(); run(); code("REVIEW_SUPERSEDED", () -> approve(old));
    }
    @Test void finalDecisionsCannotBeOverwritten() {
        ProjectReviewRun run = approve(run());
        code("REVIEW_ALREADY_DECIDED", () -> service.decide(1L, 1L, run.getId(), 1L, "CHANGES_REQUESTED", "改口", List.of()));
    }
    @Test void rejectionOfABlockedReportRecordsAnActionableReason() {
        report.setContent(""); ProjectReviewRun run = run();
        var rejected = service.decide(1L, 1L, run.getId(), 1L, "CHANGES_REQUESTED", "请补充报告正文和来源", List.of());
        assertEquals("CHANGES_REQUESTED", rejected.getStatus()); assertEquals("请补充报告正文和来源", rejected.getDecisionComment());
    }
    @Test void aNewRejectionWithdrawsAPublishedReport() {
        report.setStatus("PUBLISHED"); ProjectReviewRun run = run();
        service.decide(1L, 1L, run.getId(), 1L, "CHANGES_REQUESTED", "请补充适用范围", List.of());
        assertEquals("DRAFT", report.getStatus()); verify(reports).update(report);
    }
    @Test void failedLinkedResearchIsAnExplicitBlock() {
        report.setRunId(50L); when(reviews.researchSnapshot(1L, 50L)).thenReturn(Map.of("status", "FAILED"));
        assertTrue(run().getChecks().stream().anyMatch(check -> check.key().equals("research") && check.status().equals("BLOCKED")));
    }
    @Test void readOnlyMembersCanReadButCannotRunOrSign() {
        when(projects.hasWriteAccess(1L, 1L, 1L)).thenReturn(false);
        assertFalse(service.policy(1L, 1L, 1L).isCanManage());
        code("PROJECT_REVIEW_FORBIDDEN", this::run);
        code("PROJECT_REVIEW_FORBIDDEN", () -> service.decide(1L, 1L, 1L, 1L, "APPROVED", "同意", List.of()));
    }
    @Test void accessChecksKeepWorkspacesAndReportsIsolated() {
        code("PROJECT_NOT_FOUND", () -> service.history(2L, 1L, 1L));
        code("REPORT_NOT_FOUND", () -> service.run(1L, 1L, 999L, 1L));
    }
    @Test void publicationCannotBypassSignoffThroughReportUpdate() {
        ReportController controller = new ReportController(reports, mock(NotificationService.class), audit, service);
        var principal = new UserLoginByPassword(); principal.setId(1L);
        var auth = new UsernamePasswordAuthenticationToken(principal, null, List.of());
        code("REPORT_REVIEW_REQUIRED", () -> controller.update(1L, 1L, 100L, Map.of("status", "PUBLISHED"), auth));
        verify(reports, never()).update(any());
    }
    @Test void editingAPublishedReportReturnsItToDraft() {
        approve(run()); report.setStatus("PUBLISHED");
        ReportController controller = new ReportController(reports, mock(NotificationService.class), audit, service);
        var principal = new UserLoginByPassword(); principal.setId(1L);
        controller.update(1L, 1L, 100L, Map.of("content", "新正文 [E1]"), new UsernamePasswordAuthenticationToken(principal, null, List.of()));
        assertEquals("DRAFT", report.getStatus()); assertTrue(service.history(1L, 1L, 1L).getFirst().isStale());
    }
    @Test void publicationStatusAloneDoesNotChangeTheReviewedContent() {
        approve(run()); report.setStatus("PUBLISHED");
        assertDoesNotThrow(() -> service.assertPublishable(1L, 1L, report, 1L));
    }
    @Test void explicitReportTasksMustBeEstablishedAndAcceptedBeforeSignoff(){
        report.setContent("## 行动项\n|编号|事项|\n|---|---|\n|A01|权限回归|\n\n依据 [E1]");
        assertTrue(run().getChecks().stream().anyMatch(check->check.key().equals("actions")&&check.status().equals("BLOCKED")));
        when(reviews.actionSnapshot(1L,100L)).thenReturn(List.of(Map.of("id",1,"title","权限回归","sourceKey","item:a01","blocksRelease",true,"status","PENDING_ACCEPTANCE")));
        assertTrue(run().getChecks().stream().anyMatch(check->check.key().equals("actions")&&check.status().equals("BLOCKED")));
        when(reviews.actionSnapshot(1L,100L)).thenReturn(List.of(Map.of("id",1,"title","权限回归","sourceKey","item:a01","blocksRelease",true,"status","DONE","acceptedAt","2026-10-16","acceptedBy",1,"completionEvidence","回归记录")));
        ProjectReviewRun accepted=approve(run());assertEquals("APPROVED",accepted.getStatus());
        when(reviews.actionSnapshot(1L,100L)).thenReturn(List.of(Map.of("id",1,"title","权限回归","sourceKey","item:a01","blocksRelease",true,"status","IN_PROGRESS")));
        assertTrue(service.history(1L,1L,1L).getFirst().isStale());code("REPORT_REVIEW_STALE",()->service.assertPublishable(1L,1L,report,1L));
    }
}
