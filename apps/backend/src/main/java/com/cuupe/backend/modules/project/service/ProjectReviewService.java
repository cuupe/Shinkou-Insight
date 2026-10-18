package com.cuupe.backend.modules.project.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.entity.*;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.mapper.ProjectReviewMapper;
import com.cuupe.backend.modules.report.entity.Report;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import com.cuupe.backend.modules.actionitem.service.ReportActionExtractor;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class ProjectReviewService {
    private final ProjectMapper projects;
    private final ProjectReviewMapper reviews;
    private final ReportMapper reports;
    private final AuditLogService audit;
    private final ObjectMapper json;
    private static final Pattern LINKS = Pattern.compile("https?://[^\\s<>\\)\\]]+", Pattern.CASE_INSENSITIVE);
    private static final Pattern REFERENCES = Pattern.compile("\\[(?:E\\d+|\\d+)\\]|【(?:E)?\\d+】");
    private static final Pattern NUMBERS = Pattern.compile("\\d+(?:[.,]\\d+)*(?:%|元|万元|年|月|日|天)?");

    public ProjectReviewPolicy policy(Long workspace, Long project, Long user) {
        requireProject(workspace, project, user, false);
        ProjectReviewPolicy policy = currentPolicy(workspace, project);
        policy.setCanManage(projects.hasWriteAccess(workspace, project, user));
        return policy;
    }

    @Transactional
    public ProjectReviewPolicy savePolicy(Long workspace, Long project, Long user, ProjectReviewPolicy request) {
        requireProject(workspace, project, user, true);
        reviews.lockProject(workspace, project);
        request.setWorkspaceId(workspace); request.setProjectId(project); request.setUpdatedBy(user);
        reviews.upsertPolicy(request);
        audit.record(workspace, project, user, "PROJECT_REVIEW_POLICY_UPDATED", "PROJECT_REVIEW_POLICY", project,
                Map.of("requireCitations", request.isRequireCitations(), "verifyNumbers", request.isVerifyNumbers(),
                        "escalateConflicts", request.isEscalateConflicts(), "labelExternal", request.isLabelExternal()));
        return policy(workspace, project, user);
    }

    public List<ProjectReviewRun> history(Long workspace, Long project, Long user) {
        requireProject(workspace, project, user, false);
        ProjectReviewPolicy policy = currentPolicy(workspace, project);
        Map<Long, String> fingerprints = new HashMap<>();
        List<ProjectReviewRun> history = reviews.findHistory(workspace, project);
        for (ProjectReviewRun run : history) {
            hydrate(run);
            if (run.getReportId() == null || run.getSnapshotHash() == null) { run.setStale(true); continue; }
            String current = fingerprints.computeIfAbsent(run.getReportId(), id -> {
                Report report = reports.findById(id, project, user);
                return report == null ? "" : snapshot(project, report, policy).hash();
            });
            run.setStale(!Objects.equals(current, run.getSnapshotHash()));
        }
        return history;
    }

    public ProjectReviewRun latest(Long workspace, Long project, Long reportId, Long user) {
        return history(workspace, project, user).stream()
                .filter(run -> reportId == null || Objects.equals(reportId, run.getReportId())).findFirst().orElse(null);
    }

    @Transactional
    public ProjectReviewRun run(Long workspace, Long project, Long reportId, Long user) {
        requireProject(workspace, project, user, true);
        reviews.lockProject(workspace, project);
        if (reportId == null) {
            List<Report> available = reports.findByProject(project, user);
            if (available.isEmpty()) throw ApiException.badRequest("REVIEW_REPORT_REQUIRED", "请先生成报告，再选择报告运行审查");
            reportId = available.getFirst().getId();
        }
        Report report = requiredReport(project, reportId, user);
        ProjectReviewPolicy policy = currentPolicy(workspace, project);
        Snapshot snapshot = snapshot(project, report, policy);
        ProjectReviewRun run = new ProjectReviewRun();
        run.setWorkspaceId(workspace); run.setProjectId(project); run.setCreatedBy(user);
        run.setReportId(reportId); run.setReportTitle(report.getTitle()); run.setReportVersion(text(report.getVersionNo()));
        run.setSnapshotHash(snapshot.hash()); run.setChecks(snapshot.checks()); run.setChecksJson(write(snapshot.checks()));
        Map<String, Object> reportSnapshot = new LinkedHashMap<>();
        reportSnapshot.put("id", report.getId()); reportSnapshot.put("title", report.getTitle());
        reportSnapshot.put("versionNo", report.getVersionNo()); reportSnapshot.put("content", report.getContent());
        reportSnapshot.put("summary", report.getSummary()); reportSnapshot.put("lead", report.getLead());
        reportSnapshot.put("recommendation", report.getRecommendation()); reportSnapshot.put("recommendationDetail", report.getRecommendationDetail());
        reportSnapshot.put("citations", report.getCitations());
        run.setReportSnapshotJson(write(reportSnapshot));
        run.setAssetCount(snapshot.assets()); run.setIndexedAssetCount(snapshot.indexed());
        run.setResearchRunCount(reviews.countResearchRuns(project)); run.setReportCount(reviews.countReports(project));
        run.setEvaluationCaseCount(snapshot.evaluations()); run.setActionItemCount(reviews.countActionItems(project));
        run.setRequireCitations(policy.isRequireCitations()); run.setVerifyNumbers(policy.isVerifyNumbers());
        run.setEscalateConflicts(policy.isEscalateConflicts()); run.setLabelExternal(policy.isLabelExternal());
        run.setBlockedCount((int) snapshot.checks().stream().filter(check -> check.status().equals("BLOCKED")).count());
        run.setReviewCount((int) snapshot.checks().stream().filter(check -> check.status().equals("REVIEW")).count());
        run.setStatus(run.getBlockedCount() > 0 ? "BLOCKED" : "REVIEW");
        run.setDetail(run.getBlockedCount() > 0 ? "存在 " + run.getBlockedCount() + " 项明确缺口，请修正后重新检查。" : "结构检查完成，请逐项核验并记录签署意见。");
        reviews.insertRun(run);
        audit.record(workspace, project, user, "PROJECT_REVIEW_RUN_CREATED", "PROJECT_REVIEW_RUN", run.getId(),
                Map.of("reportId", reportId, "status", run.getStatus(), "blockedCount", run.getBlockedCount()));
        return hydrate(reviews.findRun(workspace, project, run.getId()));
    }

    @Transactional
    public ProjectReviewRun decide(Long workspace, Long project, Long id, Long user, String decision, String comment, List<String> confirmations) {
        requireProject(workspace, project, user, true);
        reviews.lockProject(workspace, project);
        ProjectReviewRun run = reviews.findRun(workspace, project, id);
        if (run == null) throw new ApiException(HttpStatus.NOT_FOUND, "REVIEW_NOT_FOUND", "审查记录不存在或无权访问");
        hydrate(run);
        if (run.getReportId() == null || run.getSnapshotHash() == null) throw ApiException.conflict("REVIEW_LEGACY", "旧版数量检查不支持签署，请对当前报告重新检查");
        if (run.getDecidedAt() != null) throw ApiException.conflict("REVIEW_ALREADY_DECIDED", "这条记录已经签署；需要修改结论时请重新检查并建立新记录");
        if (decision == null || !Set.of("APPROVED", "CHANGES_REQUESTED").contains(decision)) throw ApiException.badRequest("REVIEW_DECISION_INVALID", "审查结论只能是通过或退回修改");
        if (text(comment).isBlank() || comment.length() > 4000) throw ApiException.badRequest("REVIEW_COMMENT_REQUIRED", "请填写 1 至 4000 字的审查意见");
        ProjectReviewRun latest = reviews.findLatestForReport(workspace, project, run.getReportId());
        if (latest == null || !Objects.equals(latest.getId(), id)) throw ApiException.conflict("REVIEW_SUPERSEDED", "已有更新的检查记录，请处理最新记录");
        Report report = requiredReport(project, run.getReportId(), user);
        Snapshot current = snapshot(project, report, currentPolicy(workspace, project));
        if (!Objects.equals(current.hash(), run.getSnapshotHash())) throw ApiException.conflict("REVIEW_STALE", "报告、规则或项目依据已变化，请重新检查后签署");
        Set<String> accepted = new LinkedHashSet<>(confirmations == null ? List.of() : confirmations);
        if ("APPROVED".equals(decision)) {
            if (run.getBlockedCount() > 0) throw ApiException.conflict("REVIEW_BLOCKED", "仍有阻断项，不能签署通过；请先修正报告并重新检查");
            List<String> required = run.getChecks().stream().filter(check -> check.status().equals("REVIEW")).map(ProjectReviewCheck::key).toList();
            if (!accepted.containsAll(required)) throw ApiException.badRequest("REVIEW_CONFIRMATIONS_REQUIRED", "请逐项确认所有待人工核验的内容");
        }
        Set<String> known = new HashSet<>(run.getChecks().stream().map(ProjectReviewCheck::key).toList());
        if (!known.containsAll(accepted)) throw ApiException.badRequest("REVIEW_CONFIRMATIONS_INVALID", "确认项不属于本次审查记录");
        run.setStatus(decision); run.setDecisionComment(comment.trim()); run.setDecidedBy(user);
        run.setConfirmationsJson(write(accepted));
        if (reviews.decide(run) != 1) throw ApiException.conflict("REVIEW_ALREADY_DECIDED", "这条记录已被处理，请刷新查看");
        // A new rejection withdraws a previously published report from publication.
        if ("CHANGES_REQUESTED".equals(decision) && "PUBLISHED".equalsIgnoreCase(report.getStatus())) {
            report.setStatus("DRAFT"); reports.update(report);
        }
        audit.record(workspace, project, user, "PROJECT_REVIEW_DECIDED", "PROJECT_REVIEW_RUN", id,
                Map.of("reportId", run.getReportId(), "decision", decision, "comment", comment.trim(), "confirmations", accepted));
        return hydrate(reviews.findRun(workspace, project, id));
    }

    /** Report edits, signoff and publication share the project lock and transaction. */
    public Report lockAndLoadReport(Long workspace, Long project, Long reportId, Long user) {
        requireProject(workspace, project, user, false);
        reviews.lockProject(workspace, project);
        return requiredReport(project, reportId, user);
    }

    public void assertPublishable(Long workspace, Long project, Report report, Long user) {
        requireProject(workspace, project, user, false);
        ProjectReviewRun latest = reviews.findLatestForReport(workspace, project, report.getId());
        if (latest == null || !"APPROVED".equals(latest.getStatus()) || latest.getDecidedAt() == null || latest.getBlockedCount() > 0)
            throw ApiException.conflict("REPORT_REVIEW_REQUIRED", "请先在审查中心对当前报告完成检查和签署，再发布");
        if (!Objects.equals(latest.getSnapshotHash(), snapshot(project, report, currentPolicy(workspace, project)).hash()))
            throw ApiException.conflict("REPORT_REVIEW_STALE", "报告、规则或项目依据已变化，旧签署已失效，请重新审查后发布");
    }

    public static List<Object> reportFields(Report report) {
        return List.of(text(report.getTitle()), text(report.getVersionNo()), text(report.getLead()), text(report.getSummary()),
                text(report.getRecommendation()), text(report.getRecommendationDetail()), text(report.getContent()),
                report.getCitations() == null ? 0 : report.getCitations(), report.getRunId() == null ? "" : report.getRunId());
    }

    private record Snapshot(String hash, List<ProjectReviewCheck> checks, int assets, int indexed, int evaluations) {}
    private Snapshot snapshot(Long project, Report report, ProjectReviewPolicy policy) {
        List<Map<String, Object>> assets = reviews.assetSnapshot(project);
        List<Map<String, Object>> evaluations = reviews.evaluationSnapshot(project);
        List<Map<String,Object>> actions=reviews.actionSnapshot(project,report.getId());
        Map<String, Object> linked = report.getRunId() == null ? Map.of() : reviews.researchSnapshot(project, report.getRunId());
        if (linked == null) linked = Map.of();
        String body = text(report.getContent());
        String narrative = String.join("\n", body, text(report.getSummary()), text(report.getRecommendation()), text(report.getRecommendationDetail()));
        List<String> links = LINKS.matcher(narrative).results().map(match -> match.group()).distinct().limit(8).toList();
        int references = (int) REFERENCES.matcher(narrative).results().count();
        List<String> numericExcerpts = new ArrayList<>();
        var numbers = NUMBERS.matcher(narrative);
        while (numbers.find() && numericExcerpts.size() < 5) {
            String excerpt = narrative.substring(Math.max(0, numbers.start() - 20), Math.min(narrative.length(), numbers.end() + 30)).replace('\n', ' ');
            if (!numericExcerpts.contains(excerpt)) numericExcerpts.add(excerpt);
        }
        int indexed = (int) assets.stream().filter(asset -> "SUCCESS".equals(asset.get("indexStatus"))).count();
        List<ProjectReviewCheck> checks = new ArrayList<>();
        checks.add(check("content", "报告正文完整性", body.isBlank() ? "BLOCKED" : "PASSED", body.isBlank() ? "报告正文为空，导出内容也为空。请先补充正文。" : "报告正文已保存，可在下方逐段核验。", "project-reports", List.of()));
        boolean citationPresent = references > 0 || !links.isEmpty() || (report.getCitations() != null && report.getCitations() > 0);
        checks.add(check("citation", "引用与事实对应", !policy.isRequireCitations() ? "SKIPPED" : citationPresent ? "REVIEW" : "BLOCKED",
                !policy.isRequireCitations() ? "本次策略未启用引用检查。" : citationPresent ? "发现引用记录或来源标记；请打开原文，确认出处真实、位置可定位，并且确实支持对应结论。引用数量不能证明内容正确。" : "报告没有引用记录、正文引用标记或来源链接，请补充可定位依据。", "project-reports", links));
        checks.add(check("numbers", "数字、日期与计算", !policy.isVerifyNumbers() ? "SKIPPED" : numericExcerpts.isEmpty() ? "PASSED" : "REVIEW",
                !policy.isVerifyNumbers() ? "本次策略未启用数字检查。" : numericExcerpts.isEmpty() ? "正文未发现阿拉伯数字，中文数字及隐含数量仍需人工留意。" : "发现以下数字片段，请核对单位、适用条件、时间范围、原始值及计算结果。", "project-reports", numericExcerpts));
        checks.add(check("conflict", "冲突、假设与限制", policy.isEscalateConflicts() ? "REVIEW" : "SKIPPED",
                policy.isEscalateConflicts() ? "确认相互矛盾的来源、尚未确认的假设与资料缺口已说明；不能用建议或推断代替已核实事实。" : "本次策略未启用冲突复核。", "project-reports", List.of()));
        checks.add(check("external", "外部来源标注", policy.isLabelExternal() && !links.isEmpty() ? "REVIEW" : "SKIPPED",
                !policy.isLabelExternal() ? "本次策略未启用外部来源检查。" : links.isEmpty() ? "正文未发现网页链接。如实际使用外部材料，请在报告中补充链接与时间。" : "核对外部链接的机构、发布时间、访问时间和适用范围；本检查不会自动打开网页验证。", "project-reports", links));
        checks.add(check("research", "关联分析运行", report.getRunId() == null ? "SKIPPED" : "COMPLETED".equals(linked.get("status")) ? "PASSED" : "BLOCKED",
                report.getRunId() == null ? "此报告未关联自动分析运行，可根据已保存正文审查。" : "COMPLETED".equals(linked.get("status")) ? "关联分析已完成；其结论仍需结合正文与来源核验。" : "关联分析未完成或已失败，请先检查执行记录。", "project-runs", List.of()));
        checks.add(check("assets", "项目资料状态", assets.isEmpty() ? "SKIPPED" : indexed == assets.size() ? "PASSED" : "REVIEW",
                assets.isEmpty() ? "项目未登记知识库资料；请确认报告使用的依据已在正文中明确。" : indexed + "/" + assets.size() + " 份资料已索引。请确认未完成索引的资料是否影响当前报告。", "project-assets", List.of()));
        long unresolved = evaluations.stream().filter(item -> !"PASSED".equals(item.get("retrievalStatus"))).count();
        checks.add(check("evaluation", "检索回归结果", evaluations.isEmpty() ? "SKIPPED" : unresolved > 0 ? "REVIEW" : "PASSED",
                evaluations.isEmpty() ? "未建立检索用例，此项按需使用。" : unresolved > 0 ? "有 " + unresolved + " 条检索用例未通过或尚未运行，请确认是否影响本报告的依据。" : "已有检索用例全部通过；这仅代表资料命中，不代表回答正确。", "project-evaluation", List.of()));
        checks.add(check("scope", "结论与交付范围", "REVIEW", "确认报告回答了项目问题，事实、推断与建议区分清楚，风险及后续责任已说明。", "project-planning", List.of()));
        List<ReportActionExtractor.Draft> expected=ReportActionExtractor.extract(report);
        Set<String> imported=new HashSet<>();actions.forEach(item->imported.add(Objects.toString(item.get("sourceKey"),"")));
        long missing=expected.stream().filter(item->!imported.contains(item.sourceKey())).count();
        long pending=actions.stream().filter(item->Boolean.TRUE.equals(item.get("blocksRelease")))
                .filter(item->!"DONE".equals(item.get("status"))||item.get("acceptedAt")==null||item.get("acceptedBy")==null||Objects.toString(item.get("completionEvidence"),"").isBlank()).count();
        long followup=actions.stream().filter(item->!Boolean.TRUE.equals(item.get("blocksRelease")))
                .filter(item->!"DONE".equals(item.get("status"))||item.get("acceptedAt")==null).count();
        String actionStatus=missing+pending>0?"BLOCKED":followup>0?"REVIEW":actions.isEmpty()&&expected.isEmpty()?"SKIPPED":"PASSED";
        String actionDetail=missing+pending>0?"本报告有 "+missing+" 项任务尚未建立，"+pending+" 项发布前置任务尚未验收关闭。请先处理，再返回重新审查。":
                followup>0?"还有 "+followup+" 项任务已明确设为发布后跟进，请人工确认其不会阻断本次交付。":
                actions.isEmpty()?"报告未列出可识别的行动清单；如有其他前置工作，请手工建立关联任务。":"本报告关联的发布前置行动已验收关闭；仍需完成其他审查与人工签署。";
        checks.add(check("actions","行动项落实与验收",actionStatus,actionDetail,"project-action-items",
                actions.stream().filter(item->!"DONE".equals(item.get("status"))).map(item->Objects.toString(item.get("title"),"")).limit(8).toList()));
        String hash = hash(List.of(reportFields(report), List.of(policy.isRequireCitations(), policy.isVerifyNumbers(), policy.isEscalateConflicts(), policy.isLabelExternal()), assets, evaluations, linked,actions));
        return new Snapshot(hash, checks, assets.size(), indexed, evaluations.size());
    }
    private ProjectReviewCheck check(String key, String title, String status, String detail, String route, List<String> excerpts) {
        return new ProjectReviewCheck(key, title, status, detail, route, excerpts);
    }
    private ProjectReviewPolicy currentPolicy(Long workspace, Long project) {
        ProjectReviewPolicy policy = reviews.findPolicy(workspace, project);
        if (policy == null) { policy = new ProjectReviewPolicy(); policy.setWorkspaceId(workspace); policy.setProjectId(project); }
        return policy;
    }
    private void requireProject(Long workspace, Long project, Long user, boolean write) {
        if (projects.findAccessibleById(workspace, project, user) == null) throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        if (write && !projects.hasWriteAccess(workspace, project, user)) throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_REVIEW_FORBIDDEN", "只有项目创建者或管理员可以修改规则、运行检查及签署");
    }
    private Report requiredReport(Long project, Long id, Long user) {
        Report report = reports.findById(id, project, user);
        if (report == null) throw new ApiException(HttpStatus.NOT_FOUND, "REPORT_NOT_FOUND", "报告不存在或无权访问");
        return report;
    }
    private ProjectReviewRun hydrate(ProjectReviewRun run) {
        if (run == null) return null;
        try {
            run.setChecks(run.getChecksJson() == null ? List.of() : Arrays.asList(json.readValue(run.getChecksJson(), ProjectReviewCheck[].class)));
            run.setConfirmations(run.getConfirmationsJson() == null ? List.of() : Arrays.asList(json.readValue(run.getConfirmationsJson(), String[].class)));
            run.setReportSnapshot(run.getReportSnapshotJson() == null ? Map.of() : json.readValue(run.getReportSnapshotJson(), Map.class));
        } catch (Exception exception) { throw new IllegalStateException("无法读取已保存的审查明细", exception); }
        return run;
    }
    private String hash(Object value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(write(canonical(value)).getBytes(StandardCharsets.UTF_8))); }
        catch (Exception exception) { throw new IllegalStateException(exception); }
    }
    private Object canonical(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> sorted = new TreeMap<>(); map.forEach((key, item) -> sorted.put(String.valueOf(key), canonical(item))); return sorted;
        }
        if (value instanceof Collection<?> list) return list.stream().map(this::canonical).toList();
        return value;
    }
    private String write(Object value) { return json.writeValueAsString(value); }
    private static String text(String value) { return value == null ? "" : value; }
}
