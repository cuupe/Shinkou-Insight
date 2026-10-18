package com.cuupe.backend.modules.actionitem.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.actionitem.entity.ActionItem;
import com.cuupe.backend.modules.actionitem.mapper.ActionItemMapper;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.mapper.ProjectReviewMapper;
import com.cuupe.backend.modules.report.entity.Report;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

@Service
@RequiredArgsConstructor
public class ActionItemService {
    private final ActionItemMapper items;
    private final ProjectMapper projects;
    private final ProjectReviewMapper reviews;
    private final ReportMapper reports;
    private final AuditLogService audit;
    public record ImportItem(String sourceKey,String title,String description,String acceptanceCriteria,
                             Long ownerId,LocalDate dueAt,String priority,Boolean blocksRelease) {}
    public record ImportRequest(String sourceHash,List<ImportItem> items) {}
    public record ReportDraft(Long reportId,String reportTitle,String reportVersion,String sourceHash,
                              boolean canManage,List<ReportActionExtractor.Draft> items,List<ActionItem> existing) {}

    public boolean canManage(Long workspace,Long project,Long user) { access(workspace,project,user); return projects.hasWriteAccess(workspace,project,user); }
    public List<ActionItem> list(Long workspace,Long project,Long user,Long reportId) {
        boolean manager=canManage(workspace,project,user);
        return items.findByProject(project,user).stream().filter(item->reportId==null||Objects.equals(reportId,item.getSourceReportId()))
                .map(item->permissions(item,user,manager)).toList();
    }
    public ReportDraft draft(Long workspace,Long project,Long reportId,Long user) {
        boolean manager=canManage(workspace,project,user); Report report=report(project,reportId,user);
        return new ReportDraft(reportId,report.getTitle(),report.getVersionNo(),ReportActionExtractor.hash(report),manager,
                ReportActionExtractor.extract(report),list(workspace,project,user,reportId));
    }
    @Transactional
    public List<ActionItem> importReport(Long workspace,Long project,Long reportId,Long user,ImportRequest request) {
        manage(workspace,project,user); reviews.lockProject(workspace,project);
        Report report=report(project,reportId,user);
        if(request==null||!Objects.equals(request.sourceHash(),ReportActionExtractor.hash(report)))
            throw ApiException.conflict("ACTION_SOURCE_CHANGED","报告已变化，请重新读取任务后再导入");
        if(request.items()==null||request.items().isEmpty()||request.items().size()>100)
            throw ApiException.badRequest("ACTION_IMPORT_EMPTY","请选择1至100项任务");
        Map<String,ReportActionExtractor.Draft> candidates=new LinkedHashMap<>();
        ReportActionExtractor.extract(report).forEach(item->candidates.put(item.sourceKey(),item));
        Map<String,ActionItem> existing=new HashMap<>();
        items.findByProject(project,user).stream().filter(item->Objects.equals(reportId,item.getSourceReportId()))
                .filter(item->item.getSourceKey()!=null).forEach(item->existing.put(item.getSourceKey(),item));
        Map<String,ImportItem> selected=new LinkedHashMap<>();
        for(ImportItem input:request.items()) {
            if(input==null||!candidates.containsKey(input.sourceKey())) throw ApiException.badRequest("ACTION_SOURCE_INVALID","任务不属于当前报告的行动清单");
            selected.putIfAbsent(input.sourceKey(),input);
        }
        for(var source:candidates.values()) {
            ImportItem input=selected.get(source.sourceKey());
            if(input==null||existing.containsKey(source.sourceKey())) continue;
            ActionItem item=new ActionItem();
            item.setTitle(input.title()); item.setDescription(input.description()); item.setAcceptanceCriteria(input.acceptanceCriteria());
            item.setOwnerId(input.ownerId()); item.setDueAt(input.dueAt()); item.setPriority(input.priority());
            item.setBlocksRelease(input.blocksRelease()==null||input.blocksRelease());
            item.setSourceReportId(reportId);item.setSourceKey(input.sourceKey());item.setSourceReportVersion(report.getVersionNo());
            item.setSourceExcerpt(source.sourceExcerpt());
            insert(workspace,project,user,item);
        }
        return list(workspace,project,user,reportId);
    }
    @Transactional
    public ActionItem create(Long workspace,Long project,Long user,ActionItem input) {
        manage(workspace,project,user);reviews.lockProject(workspace,project);
        ActionItem item=new ActionItem();
        item.setTitle(input.getTitle());item.setDescription(input.getDescription());item.setAcceptanceCriteria(input.getAcceptanceCriteria());
        item.setOwnerId(input.getOwnerId());item.setDueAt(input.getDueAt());item.setPriority(input.getPriority());
        item.setBlocksRelease(input.getBlocksRelease()==null||input.getBlocksRelease());
        if(input.getSourceReviewRunId()!=null&&input.getSourceReportId()==null)
            throw ApiException.badRequest("ACTION_SOURCE_INVALID","关联审查记录时必须同时关联来源报告");
        if(input.getSourceReportId()!=null) {
            Report source=report(project,input.getSourceReportId(),user);
            item.setSourceReportId(source.getId());item.setSourceReportVersion(source.getVersionNo());
            if(input.getSourceReviewRunId()!=null) {
                var review=reviews.findRun(workspace,project,input.getSourceReviewRunId());
                if(review==null||!Objects.equals(review.getReportId(),source.getId()))
                    throw ApiException.badRequest("ACTION_SOURCE_INVALID","审查记录与来源报告不匹配");
                item.setSourceReviewRunId(review.getId());item.setSourceKey("review:"+review.getId());
                ActionItem existing=items.findByProject(project,user).stream()
                    .filter(row->Objects.equals(row.getSourceReportId(),source.getId())&&Objects.equals(row.getSourceKey(),item.getSourceKey()))
                    .findFirst().orElse(null);
                if(existing!=null) return permissions(existing,user,true);
            }
        }
        insert(workspace,project,user,item);return required(project,item.getId(),user,true);
    }
    private void insert(Long workspace,Long project,Long user,ActionItem item) {
        item.setProjectId(project);item.setCreatedBy(user);item.setStatus("DRAFT"); validate(workspace,project,item);
        if(items.insert(item)!=1) throw ApiException.conflict("ACTION_NOT_CREATED","任务创建失败，请刷新后重试");
        withdrawIfBlocking(workspace,project,user,item);
        audit.record(workspace,project,user,"ACTION_ITEM_CREATED","ACTION_ITEM",item.getId(),Map.of("title",item.getTitle()));
    }
    @Transactional
    public ActionItem update(Long workspace,Long project,Long id,Long user,Map<String,Object> body) {
        boolean manager=canManage(workspace,project,user);reviews.lockProject(workspace,project);
        ActionItem item=required(project,id,user,manager);
        if(!item.isCanEdit()) forbidden();
        Set<String> metadata=Set.of("title","description","ownerId","dueAt","priority","acceptanceCriteria","blocksRelease");
        boolean editing=body.keySet().stream().anyMatch(metadata::contains);
        if(editing&&!manager) forbidden();
        if(editing&&("PENDING_ACCEPTANCE".equals(item.getStatus())||("DONE".equals(item.getStatus())&&item.getAcceptedAt()!=null)))
            throw ApiException.conflict("ACTION_LOCKED","请先重新打开或退回任务，再修改任务与验收标准");
        if(body.containsKey("title")) item.setTitle(text(body.get("title")));
        if(body.containsKey("description")) item.setDescription(text(body.get("description")));
        if(body.containsKey("acceptanceCriteria")) item.setAcceptanceCriteria(text(body.get("acceptanceCriteria")));
        if(body.containsKey("ownerId")) item.setOwnerId(number(body.get("ownerId")));
        if(body.containsKey("dueAt")) item.setDueAt(date(body.get("dueAt")));
        if(body.containsKey("priority")) item.setPriority(text(body.get("priority")));
        if(body.containsKey("blocksRelease")) {
            if(!(body.get("blocksRelease") instanceof Boolean value)) throw ApiException.badRequest("ACTION_INVALID","发布前置条件必须是布尔值");
            item.setBlocksRelease(value);
        }
        if(body.containsKey("status")) {
            String next=text(body.get("status")).toUpperCase(Locale.ROOT).replace('-','_');
            if(!"IN_PROGRESS".equals(next)) throw ApiException.badRequest("ACTION_TRANSITION","完成任务需先提交证据，再由项目管理者验收");
            if("PENDING_ACCEPTANCE".equals(item.getStatus())) throw ApiException.conflict("ACTION_TRANSITION","请等待验收或退回修改");
            if("DONE".equals(item.getStatus())&&!manager) forbidden();
            if(item.getOwnerId()==null) throw ApiException.badRequest("ACTION_OWNER_REQUIRED","请先分派实际负责人，再开始处理");
            item.setStatus("IN_PROGRESS");item.setAcceptedAt(null);item.setAcceptedBy(null);item.setAcceptanceComment(null);
            item.setSubmittedAt(null);item.setSubmittedBy(null);
        }
        validate(workspace,project,item);save(workspace,project,user,item,"ACTION_ITEM_UPDATED");
        return required(project,id,user,manager);
    }
    @Transactional
    public ActionItem submit(Long workspace,Long project,Long id,Long user,String evidence) {
        boolean manager=canManage(workspace,project,user);reviews.lockProject(workspace,project);
        ActionItem item=required(project,id,user,manager);if(!item.isCanEdit()) forbidden();
        if(!Set.of("IN_PROGRESS","REJECTED").contains(item.getStatus()))
            throw ApiException.conflict("ACTION_TRANSITION","请先开始处理任务，再提交完成证据");
        item.setCompletionEvidence(requiredText(evidence,8000,"请填写可核对的完成记录或证据链接"));
        if(item.getOwnerId()==null) throw ApiException.badRequest("ACTION_OWNER_REQUIRED","请先分派实际负责人");
        item.setSubmittedBy(user);item.setSubmittedAt(LocalDateTime.now());item.setStatus("PENDING_ACCEPTANCE");
        item.setAcceptedAt(null);item.setAcceptedBy(null);item.setAcceptanceComment(null);
        save(workspace,project,user,item,"ACTION_ITEM_SUBMITTED");return required(project,id,user,manager);
    }
    @Transactional
    public ActionItem accept(Long workspace,Long project,Long id,Long user,String decision,String comment) {
        manage(workspace,project,user);reviews.lockProject(workspace,project);
        ActionItem item=required(project,id,user,true);
        if(!"PENDING_ACCEPTANCE".equals(item.getStatus())) throw ApiException.conflict("ACTION_TRANSITION","任务尚未提交验收或已被处理，请刷新查看");
        String note=requiredText(comment,4000,"请记录验收或退回意见");
        if(!Set.of("ACCEPT","RETURN").contains(text(decision))) throw ApiException.badRequest("ACTION_DECISION_INVALID","请选择验收通过或退回修改");
        if("ACCEPT".equals(decision)) {
            requiredText(item.getCompletionEvidence(),8000,"任务没有完成证据，不能验收通过");
            if(item.getSubmittedAt()==null) throw ApiException.conflict("ACTION_TRANSITION","任务缺少提交记录，请重新提交验收");
            item.setStatus("DONE");item.setAcceptedBy(user);item.setAcceptedAt(LocalDateTime.now());
        } else { item.setStatus("REJECTED");item.setAcceptedBy(null);item.setAcceptedAt(null); }
        item.setAcceptanceComment(note);save(workspace,project,user,item,"ACTION_ITEM_"+("ACCEPT".equals(decision)?"ACCEPTED":"RETURNED"));
        return required(project,id,user,true);
    }
    private void save(Long workspace,Long project,Long user,ActionItem item,String event) {
        if(items.update(item)!=1) throw ApiException.conflict("ACTION_CHANGED","任务已变化，请刷新后重试");
        withdrawIfBlocking(workspace,project,user,item);
        Map<String,Object> details=new LinkedHashMap<>();
        details.put("status",item.getStatus());details.put("sourceReportId",item.getSourceReportId());
        details.put("ownerId",item.getOwnerId());details.put("acceptanceCriteria",item.getAcceptanceCriteria());
        details.put("completionEvidence",item.getCompletionEvidence());details.put("acceptanceComment",item.getAcceptanceComment());
        details.put("submittedBy",item.getSubmittedBy());details.put("acceptedBy",item.getAcceptedBy());
        audit.record(workspace,project,user,event,"ACTION_ITEM",item.getId(),details);
    }
    private void withdrawIfBlocking(Long workspace,Long project,Long user,ActionItem item) {
        if(item.getSourceReportId()==null||!Boolean.TRUE.equals(item.getBlocksRelease())||"DONE".equals(item.getStatus())) return;
        Report source=report(project,item.getSourceReportId(),user);
        if("PUBLISHED".equalsIgnoreCase(source.getStatus())) {
            source.setStatus("DRAFT");reports.update(source);
            audit.record(workspace,project,user,"REPORT_WITHDRAWN_FOR_ACTION","REPORT",source.getId());
        }
    }
    private void validate(Long workspace,Long project,ActionItem item) {
        item.setTitle(requiredText(item.getTitle(),255,"请填写1至255字的行动项名称"));
        if(text(item.getDescription()).length()>1000) throw ApiException.badRequest("ACTION_INVALID","背景说明不能超过1000字");
        item.setDescription(text(item.getDescription()));
        item.setAcceptanceCriteria(requiredText(item.getAcceptanceCriteria(),4000,"请填写明确的验收标准（最多4000字）"));
        item.setPriority(switch(text(item.getPriority()).toLowerCase(Locale.ROOT)) { case "高","high"->"HIGH";case "低","low"->"LOW";case "","中","medium","normal"->"MEDIUM";default->throw ApiException.badRequest("ACTION_INVALID","优先级不正确"); });
        if(item.getOwnerId()!=null&&projects.findAccessibleById(workspace,project,item.getOwnerId())==null)
            throw ApiException.badRequest("ACTION_OWNER_INVALID","负责人必须是能访问本项目的实际成员");
    }
    private ActionItem required(Long project,Long id,Long user,boolean manager) {
        ActionItem item=items.findById(id,project,user);
        if(item==null) throw new ApiException(HttpStatus.NOT_FOUND,"ACTION_ITEM_NOT_FOUND","行动项不存在或无权访问");
        return permissions(item,user,manager);
    }
    private ActionItem permissions(ActionItem item,Long user,boolean manager) {
        item.setCanManage(manager);item.setCanEdit(manager||Objects.equals(user,item.getOwnerId()));
        item.setCanAccept(manager&&"PENDING_ACCEPTANCE".equals(item.getStatus()));return item;
    }
    private Report report(Long project,Long id,Long user) {
        Report report=reports.findById(id,project,user);
        if(report==null) throw new ApiException(HttpStatus.NOT_FOUND,"REPORT_NOT_FOUND","来源报告不存在或无权访问");return report;
    }
    private void access(Long workspace,Long project,Long user) {
        if(projects.findAccessibleById(workspace,project,user)==null) throw new ApiException(HttpStatus.NOT_FOUND,"PROJECT_NOT_FOUND","项目不存在或无权访问");
    }
    private void manage(Long workspace,Long project,Long user) { if(!canManage(workspace,project,user)) forbidden(); }
    private void forbidden() { throw new ApiException(HttpStatus.FORBIDDEN,"ACTION_FORBIDDEN","仅任务负责人可以推进，项目创建者或管理员可以分派和验收"); }
    private static String text(Object value) { return value==null?"":String.valueOf(value); }
    private static String requiredText(String value,int max,String message) {
        String result=text(value).trim();if(result.isBlank()||result.length()>max) throw ApiException.badRequest("ACTION_INVALID",message);return result;
    }
    private static Long number(Object value) {
        if(value==null||text(value).isBlank()) return null;
        try { return Long.valueOf(text(value)); } catch(NumberFormatException e) { throw ApiException.badRequest("ACTION_INVALID","负责人编号不正确"); }
    }
    private static LocalDate date(Object value) {
        if(value==null||text(value).isBlank()) return null;
        try { return LocalDate.parse(text(value)); }
        catch(java.time.format.DateTimeParseException e) { throw ApiException.badRequest("ACTION_INVALID","截止日期格式应为YYYY-MM-DD"); }
    }
}
