package com.cuupe.backend.modules.actionitem.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.actionitem.entity.ActionItem;
import com.cuupe.backend.modules.actionitem.mapper.ActionItemMapper;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.entity.Project;
import com.cuupe.backend.modules.project.entity.ProjectReviewRun;
import com.cuupe.backend.modules.project.mapper.*;
import com.cuupe.backend.modules.report.entity.Report;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import org.junit.jupiter.api.*;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ActionItemServiceTest {
 final ActionItemMapper mapper=mock(ActionItemMapper.class);
 final ProjectMapper projects=mock(ProjectMapper.class);
 final ProjectReviewMapper reviews=mock(ProjectReviewMapper.class);
 final ReportMapper reports=mock(ReportMapper.class);
 final AuditLogService audit=mock(AuditLogService.class);
 final ActionItemService service=new ActionItemService(mapper,projects,reviews,reports,audit);
 final Map<Long,ActionItem> records=new LinkedHashMap<>();final Report report=new Report();
 static final String BODY="""
     ## 成本
     |编号|项目|金额|
     |---|---|---|
     |C01|平台|36000|
     ## 五、行动项
     |编号|事项|责任人|截止日期|验收标准|状态|
     |---|---|---|---|---|---|
     |A01|权限撤销传播回归|林澈/IT|2026-10-20|移出后检索和详情均拒绝|待处理|
     |A02|故障处置演练|周策/运维|2026-10-21|留存演练记录|已完成|
     ## 结论
     不批准生产上线。
     """;
 @BeforeEach void setup(){
  Project project=new Project();project.setId(1L);
  for(long user:List.of(1L,2L,3L))when(projects.findAccessibleById(1L,1L,user)).thenReturn(project);
  when(projects.hasWriteAccess(1L,1L,1L)).thenReturn(true);
  report.setId(10L);report.setProjectId(1L);report.setTitle("验收报告");report.setContent(BODY);report.setVersionNo("1");report.setStatus("DRAFT");
  when(reports.findById(10L,1L,1L)).thenReturn(report);when(reports.findById(10L,1L,2L)).thenReturn(report);
  when(mapper.findByProject(eq(1L),anyLong())).thenAnswer(inv->new ArrayList<>(records.values()));
  when(mapper.findById(anyLong(),eq(1L),anyLong())).thenAnswer(inv->records.get(inv.getArgument(0)));
  when(mapper.insert(any())).thenAnswer(inv->{ActionItem item=inv.getArgument(0);item.setId((long)records.size()+1);records.put(item.getId(),item);return 1;});
  when(mapper.update(any())).thenReturn(1);
 }
 ActionItem input(){ActionItem item=new ActionItem();item.setTitle("权限回归");item.setAcceptanceCriteria("移出成员无法检索资料");item.setOwnerId(2L);item.setSourceReportId(10L);return item;}
 void code(String expected,Runnable operation){assertEquals(expected,assertThrows(ApiException.class,operation::run).getCode());}
 @Test void extractorPreservesOrderAndDoesNotInterpretDocumentStatusAsAcceptance(){
  var drafts=ReportActionExtractor.extract(report);assertEquals(List.of("item:a01","item:a02"),drafts.stream().map(ReportActionExtractor.Draft::sourceKey).toList());
  assertEquals("权限撤销传播回归",drafts.getFirst().title());assertEquals(LocalDate.parse("2026-10-20"),drafts.getFirst().dueAt());
  assertEquals("移出后检索和详情均拒绝",drafts.getFirst().acceptanceCriteria());assertEquals("故障处置演练",drafts.get(1).title());
 }
 @Test void explicitBulletActionsWorkButOtherReportListsAreNotImported(){
  report.setContent("## 风险\n- 不属于任务\n## 后续行动\n- [x] 补齐回归证据\n1. 核对预算\n## 总结\n- 不属于任务");
  assertEquals(List.of("补齐回归证据","核对预算"),ReportActionExtractor.extract(report).stream().map(ReportActionExtractor.Draft::title).toList());
 }
 @Test void importIsScopedOrderedAndIdempotent(){
  var source=service.draft(1L,1L,10L,1L);
  var selected=source.items().stream().map(item->new ActionItemService.ImportItem(item.sourceKey(),item.title(),item.description(),item.acceptanceCriteria(),2L,item.dueAt(),item.priority(),true)).toList();
  var reversed=new ArrayList<>(selected);Collections.reverse(reversed);
  var request=new ActionItemService.ImportRequest(source.sourceHash(),reversed);
  service.importReport(1L,1L,10L,1L,request);service.importReport(1L,1L,10L,1L,request);
  assertEquals(2,records.size());verify(mapper,times(2)).insert(any());
  assertEquals(List.of("权限撤销传播回归","故障处置演练"),records.values().stream().map(ActionItem::getTitle).toList());
  assertTrue(records.values().stream().allMatch(item->"DRAFT".equals(item.getStatus())&&item.getAcceptedAt()==null));
  assertEquals(10L,records.get(1L).getSourceReportId());assertNotNull(records.get(1L).getSourceExcerpt());
 }
 @Test void codeExamplesAreNotTasksAndBlankDetailFallsBackToRecommendation(){
  report.setContent("```markdown\n## 行动项\n- 示例任务\n```\n## 后续行动\n- 实际任务");
  assertEquals(List.of("实际任务"),ReportActionExtractor.extract(report).stream().map(ReportActionExtractor.Draft::title).toList());
  report.setContent("");report.setRecommendationDetail("");report.setRecommendation("- 核对回归结果");
  assertEquals("核对回归结果",ReportActionExtractor.extract(report).getFirst().title());
 }
 @Test void sourceChangesAndInventedSourceKeysCannotBeImported(){
  var old=service.draft(1L,1L,10L,1L);report.setContent(BODY+"变更");
  code("ACTION_SOURCE_CHANGED",()->service.importReport(1L,1L,10L,1L,new ActionItemService.ImportRequest(old.sourceHash(),List.of())));
  var fake=new ActionItemService.ImportItem("other-report-key","伪造","","标准",2L,null,"HIGH",true);
  code("ACTION_SOURCE_INVALID",()->service.importReport(1L,1L,10L,1L,new ActionItemService.ImportRequest(ReportActionExtractor.hash(report),List.of(fake))));
  verify(mapper,never()).insert(any());
 }
 @Test void completionRequiresExecutionEvidenceAndExplicitManagerAcceptance(){
  ActionItem item=service.create(1L,1L,1L,input());
  code("ACTION_TRANSITION",()->service.update(1L,1L,item.getId(),2L,Map.of("status","DONE")));
  service.update(1L,1L,item.getId(),2L,Map.of("status","IN_PROGRESS"));
  code("ACTION_INVALID",()->service.submit(1L,1L,item.getId(),2L," "));
  service.submit(1L,1L,item.getId(),2L,"测试会话A移出后403，会话B仍成功，记录 /tmp/permission-test.txt");
  assertEquals("PENDING_ACCEPTANCE",item.getStatus());assertNotNull(item.getSubmittedAt());assertNull(item.getAcceptedAt());
  code("ACTION_FORBIDDEN",()->service.accept(1L,1L,item.getId(),2L,"ACCEPT","自行通过"));
  code("ACTION_INVALID",()->service.accept(1L,1L,item.getId(),1L,"ACCEPT",""));
  service.accept(1L,1L,item.getId(),1L,"ACCEPT","已核对两会话记录与标准");
  assertEquals("DONE",item.getStatus());assertEquals(1L,item.getAcceptedBy());assertNotNull(item.getAcceptedAt());
  code("ACTION_TRANSITION",()->service.accept(1L,1L,item.getId(),1L,"ACCEPT","重复验收"));
 }
 @Test void returnAndReopenNeverRetainAnOldAcceptance(){
  ActionItem item=service.create(1L,1L,1L,input());
  service.update(1L,1L,item.getId(),2L,Map.of("status","IN_PROGRESS"));service.submit(1L,1L,item.getId(),2L,"回归记录");
  service.accept(1L,1L,item.getId(),1L,"RETURN","缺少第二个会话的验证");assertEquals("REJECTED",item.getStatus());
  service.submit(1L,1L,item.getId(),2L,"补齐两个会话的完整验证记录");service.accept(1L,1L,item.getId(),1L,"ACCEPT","已核对");
  report.setStatus("PUBLISHED");service.update(1L,1L,item.getId(),1L,Map.of("status","IN_PROGRESS"));
  assertNull(item.getAcceptedAt());assertNull(item.getAcceptedBy());assertEquals("DRAFT",report.getStatus());
 }
 @Test void crossProjectReferencesAndForeignAssigneesAreRejected(){
  ActionItem item=input();item.setSourceReportId(99L);code("REPORT_NOT_FOUND",()->service.create(1L,1L,1L,item));
  item.setSourceReportId(10L);item.setOwnerId(99L);code("ACTION_OWNER_INVALID",()->service.create(1L,1L,1L,item));
  code("PROJECT_NOT_FOUND",()->service.list(2L,1L,1L,null));
 }
 @Test void readersCannotChangeTasksAndExecutorsCannotChangeAcceptanceCriteria(){
  ActionItem item=service.create(1L,1L,1L,input());
  code("ACTION_FORBIDDEN",()->service.update(1L,1L,item.getId(),3L,Map.of("status","IN_PROGRESS")));
  code("ACTION_FORBIDDEN",()->service.update(1L,1L,item.getId(),2L,Map.of("acceptanceCriteria","降低标准")));
 }
 @Test void legacyCompletionWithoutAcceptanceCanHaveItsMissingCriteriaRepaired(){
  ActionItem item=service.create(1L,1L,1L,input());item.setStatus("DONE");item.setAcceptanceCriteria(null);
  service.update(1L,1L,item.getId(),1L,Map.of("acceptanceCriteria","补齐旧任务的可核验完成标准"));
  assertNull(item.getAcceptedAt());service.update(1L,1L,item.getId(),1L,Map.of("status","IN_PROGRESS"));
  assertEquals("IN_PROGRESS",item.getStatus());
 }
 @Test void reviewOriginMustMatchTheReportAndRepeatedCreationDoesNotDuplicate(){
  var review=new ProjectReviewRun();review.setId(5L);review.setReportId(11L);when(reviews.findRun(1L,1L,5L)).thenReturn(review);
  ActionItem item=input();item.setSourceReviewRunId(5L);code("ACTION_SOURCE_INVALID",()->service.create(1L,1L,1L,item));
  review.setReportId(10L);var created=service.create(1L,1L,1L,item);assertEquals(created.getId(),service.create(1L,1L,1L,item).getId());
  verify(mapper,times(1)).insert(any());assertEquals(5L,created.getSourceReviewRunId());
 }
}
