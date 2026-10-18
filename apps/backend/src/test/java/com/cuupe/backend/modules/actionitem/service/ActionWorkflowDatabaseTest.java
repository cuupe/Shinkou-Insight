package com.cuupe.backend.modules.actionitem.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.actionitem.mapper.ActionItemMapper;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.project.entity.ProjectReviewCheck;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.mapper.ProjectReviewMapper;
import com.cuupe.backend.modules.project.service.ProjectReviewService;
import com.cuupe.backend.modules.report.controller.ReportController;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.mapping.Environment;
import org.apache.ibatis.session.*;
import org.apache.ibatis.transaction.jdbc.JdbcTransactionFactory;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import tools.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** Real SQL and services, isolated project, unconditional rollback including temporary migration DDL. */
@EnabledIfSystemProperty(named="action.integration",matches="true")
class ActionWorkflowDatabaseTest {
 @Test void reportImportExecutionAcceptanceReviewAndPublicationFormOneClosedLoop() throws Exception {
  PGSimpleDataSource db=new PGSimpleDataSource();
  db.setURL(System.getenv().getOrDefault("SHINKOU_DB_URL","jdbc:postgresql://localhost:15432/shinkou_insight"));
  db.setUser(System.getenv().getOrDefault("SHINKOU_DB_USERNAME","postgres"));
  db.setPassword(System.getenv().getOrDefault("SHINKOU_DB_PASSWORD","shinkou_dev_password"));
  Configuration config=new Configuration(new Environment("action-rollback-test",new JdbcTransactionFactory(),db));
  config.setMapUnderscoreToCamelCase(true);
  for(String resource:List.of("mapper/project/ProjectMapper.xml","mapper/report/ReportMapper.xml","mapper/actionitem/ActionItemMapper.xml")) {
   try(var source=getClass().getClassLoader().getResourceAsStream(resource)) {
    assertNotNull(source);new XMLMapperBuilder(source,config,resource,config.getSqlFragments()).parse();
   }
  }
  config.addMapper(ProjectReviewMapper.class);
  try(SqlSession session=new SqlSessionFactoryBuilder().build(config).openSession(false)) {
   try {
    Connection connection=session.getConnection();
    try(var columns=connection.getMetaData().getColumns(null,"public","action_items","source_report_id")) {
     if(!columns.next())try(var source=getClass().getClassLoader().getResourceAsStream("db/migration/V35__action_item_delivery_workflow.sql");var statement=connection.createStatement()) {
      assertNotNull(source);statement.execute(new String(source.readAllBytes(),StandardCharsets.UTF_8));
     }
    }
    long workspace,user,project,reportId;
    try(var statement=connection.createStatement();var rows=statement.executeQuery("SELECT workspace_id,user_id FROM workspace_members WHERE status='ACTIVE' ORDER BY workspace_id,user_id LIMIT 1")) {
     assertTrue(rows.next());workspace=rows.getLong(1);user=rows.getLong(2);
    }
    try(var statement=connection.prepareStatement("INSERT INTO projects(workspace_id,code,name,created_by,visibility) VALUES(?,?,?,?,'WORKSPACE') RETURNING id")) {
     statement.setLong(1,workspace);statement.setString(2,"action-qa-"+UUID.randomUUID().toString().substring(0,12));statement.setString(3,"行动项闭环回滚测试");statement.setLong(4,user);
     try(var rows=statement.executeQuery()){assertTrue(rows.next());project=rows.getLong(1);}
    }
    String content="""
        # 验收报告
        依据测试回归方案 [E1] 进行验收。
        ## 后续行动
        |编号|事项|责任人|截止日期|验收标准|状态|
        |---|---|---|---|---|---|
        |A01|权限撤销回归|测试负责人|2026-10-20|撤销后两会话均拒绝|待处理|
        |A02|应急演练|运维负责人|2026-10-21|演练记录完整|已完成|
        |A03|合规复核|合规负责人|2026-10-22|完成复核签字|待处理|
        """;
    try(var statement=connection.prepareStatement("INSERT INTO reports(project_id,title,status,content,created_by,version_no) VALUES(?,'行动项测试报告','DRAFT',?,?,'1') RETURNING id")) {
     statement.setLong(1,project);statement.setString(2,content);statement.setLong(3,user);
     try(var rows=statement.executeQuery()){assertTrue(rows.next());reportId=rows.getLong(1);}
    }
    var projects=session.getMapper(ProjectMapper.class);var reports=session.getMapper(ReportMapper.class);var reviews=session.getMapper(ProjectReviewMapper.class);
    var audit=mock(AuditLogService.class);
    var actions=new ActionItemService(session.getMapper(ActionItemMapper.class),projects,reviews,reports,audit);
    var reviewService=new ProjectReviewService(projects,reviews,reports,audit,new ObjectMapper());
    var initial=reviewService.run(workspace,project,reportId,user);
    assertEquals("BLOCKED",initial.getChecks().stream().filter(check->check.key().equals("actions")).findFirst().orElseThrow().status());
    var source=actions.draft(workspace,project,reportId,user);assertEquals(3,source.items().size());
    var selected=new ArrayList<>(source.items().stream().map(item->new ActionItemService.ImportItem(item.sourceKey(),item.title(),item.description(),item.acceptanceCriteria(),user,item.dueAt(),item.priority(),true)).toList());
    Collections.reverse(selected);
    var request=new ActionItemService.ImportRequest(source.sourceHash(),selected);
    var imported=actions.importReport(workspace,project,reportId,user,request);
    assertEquals(List.of("item:a01","item:a02","item:a03"),imported.stream().map(item->item.getSourceKey()).toList());
    assertEquals(3,actions.importReport(workspace,project,reportId,user,request).size());
    assertEquals(3,actions.list(workspace,project,user,reportId).size());
    assertEquals(0,actions.list(workspace,project,user,-1L).size());
    assertTrue(reviewService.history(workspace,project,user).getFirst().isStale());
    for(var item:imported) {
     assertEquals("DRAFT",item.getStatus());assertEquals("行动项测试报告",item.getSourceReportTitle());
     actions.update(workspace,project,item.getId(),user,Map.of("status","IN_PROGRESS"));
     actions.submit(workspace,project,item.getId(),user,"回归记录：各项断言与验收标准对应，附件 test-record.txt");
     assertTrue(actions.list(workspace,project,user,reportId).stream().filter(row->row.getId().equals(item.getId())).findFirst().orElseThrow().isCanAccept());
     var pending=reviewService.run(workspace,project,reportId,user);assertTrue(pending.getBlockedCount()>0);
     if(item==imported.getFirst()) {
      actions.accept(workspace,project,item.getId(),user,"RETURN","补齐第二个会话记录");
      assertEquals("REJECTED",actions.list(workspace,project,user,reportId).getFirst().getStatus());
      actions.submit(workspace,project,item.getId(),user,"补齐双会话回归断言与复核记录");
     }
     var accepted=actions.accept(workspace,project,item.getId(),user,"ACCEPT","已核对证据与验收标准");
     assertEquals("DONE",accepted.getStatus());assertNotNull(accepted.getAcceptedAt());assertNotNull(accepted.getAcceptedByName());
    }
    var ready=reviewService.run(workspace,project,reportId,user);assertEquals(0,ready.getBlockedCount(),ready.getChecks().toString());
    assertEquals("PASSED",ready.getChecks().stream().filter(check->check.key().equals("actions")).findFirst().orElseThrow().status());
    var confirmations=ready.getChecks().stream().filter(check->check.status().equals("REVIEW")).map(ProjectReviewCheck::key).toList();
    reviewService.decide(workspace,project,ready.getId(),user,"APPROVED","已核实行动项验收证据与报告依据",confirmations);
    var principal=new UserLoginByPassword();principal.setId(user);
    var auth=new UsernamePasswordAuthenticationToken(principal,null,List.of());
    var controller=new ReportController(reports,mock(NotificationService.class),audit,reviewService);
    controller.update(workspace,project,reportId,Map.of("status","PUBLISHED"),auth);
    assertEquals("PUBLISHED",reports.findById(reportId,project,user).getStatus());
    actions.update(workspace,project,imported.getFirst().getId(),user,Map.of("status","IN_PROGRESS"));
    assertEquals("DRAFT",reports.findById(reportId,project,user).getStatus());
    assertTrue(reviewService.history(workspace,project,user).getFirst().isStale());
    assertEquals("REPORT_REVIEW_STALE",assertThrows(ApiException.class,()->controller.update(workspace,project,reportId,Map.of("status","PUBLISHED"),auth)).getCode());
    assertEquals(content,reports.findById(reportId,project,user).getContent());
   } finally {session.rollback(true);}
  }
 }
}
