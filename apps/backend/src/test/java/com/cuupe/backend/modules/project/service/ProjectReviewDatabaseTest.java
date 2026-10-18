package com.cuupe.backend.modules.project.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.project.entity.ProjectReviewCheck;
import com.cuupe.backend.modules.project.entity.ProjectReviewRun;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.mapper.ProjectReviewMapper;
import com.cuupe.backend.modules.report.controller.ReportController;
import com.cuupe.backend.modules.report.mapper.ReportMapper;
import com.cuupe.backend.modules.notification.service.NotificationService;
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

/** Uses an isolated project and rolls back every row and any temporary DDL. */
@EnabledIfSystemProperty(named="review.integration", matches="true")
class ProjectReviewDatabaseTest {
    @Test void realPostgresPersistsChecksAndSignoffAndEnforcesPublicationAndInvalidation() throws Exception {
        PGSimpleDataSource dataSource = new PGSimpleDataSource();
        dataSource.setURL(System.getenv().getOrDefault("SHINKOU_DB_URL", "jdbc:postgresql://localhost:15432/shinkou_insight"));
        dataSource.setUser(System.getenv().getOrDefault("SHINKOU_DB_USERNAME", "postgres"));
        dataSource.setPassword(System.getenv().getOrDefault("SHINKOU_DB_PASSWORD", "shinkou_dev_password"));
        Configuration configuration = new Configuration(new Environment("review-rollback-test", new JdbcTransactionFactory(), dataSource));
        configuration.setMapUnderscoreToCamelCase(true);
        for (String resource : List.of("mapper/project/ProjectMapper.xml", "mapper/report/ReportMapper.xml")) {
            try (var stream = getClass().getClassLoader().getResourceAsStream(resource)) {
                assertNotNull(stream, resource); new XMLMapperBuilder(stream, configuration, resource, configuration.getSqlFragments()).parse();
            }
        }
        configuration.addMapper(ProjectReviewMapper.class);
        try (SqlSession session = new SqlSessionFactoryBuilder().build(configuration).openSession(false)) {
            try {
                Connection connection = session.getConnection();
                try (var columns = connection.getMetaData().getColumns(null, "public", "project_review_runs", "report_id")) {
                    if (!columns.next()) {
                        try (var source = getClass().getClassLoader().getResourceAsStream("db/migration/V34__report_review_signoff.sql"); var statement = connection.createStatement()) {
                            assertNotNull(source); statement.execute(new String(source.readAllBytes(), StandardCharsets.UTF_8));
                        }
                    }
                }
                long workspace, user, project, reportId;
                try (var columns = connection.getMetaData().getColumns(null, "public", "action_items", "source_report_id")) {
                    if (!columns.next()) {
                        try (var source = getClass().getClassLoader().getResourceAsStream("db/migration/V35__action_item_delivery_workflow.sql"); var statement = connection.createStatement()) {
                            assertNotNull(source); statement.execute(new String(source.readAllBytes(), StandardCharsets.UTF_8));
                        }
                    }
                }
                try (var statement = connection.createStatement(); var rows = statement.executeQuery("SELECT workspace_id,user_id FROM workspace_members WHERE status='ACTIVE' ORDER BY workspace_id,user_id LIMIT 1")) {
                    assertTrue(rows.next(), "The local fixture database needs an active workspace member"); workspace = rows.getLong(1); user = rows.getLong(2);
                }
                try (var statement = connection.prepareStatement("INSERT INTO projects(workspace_id,code,name,created_by,visibility) VALUES(?,?,?,?,'WORKSPACE') RETURNING id")) {
                    statement.setLong(1, workspace); statement.setString(2, "review-qa-" + UUID.randomUUID().toString().substring(0, 12)); statement.setString(3, "审查回滚验证"); statement.setLong(4, user);
                    try (var rows = statement.executeQuery()) { assertTrue(rows.next()); project = rows.getLong(1); }
                }
                try (var statement = connection.prepareStatement("INSERT INTO reports(project_id,title,status,content,created_by,citations,version_no) VALUES(?,'审查回滚测试报告','DRAFT','住宿上限为800元 [E1]，条件须核对。',?,1,'1') RETURNING id")) {
                    statement.setLong(1, project); statement.setLong(2, user); try (var rows = statement.executeQuery()) { assertTrue(rows.next()); reportId = rows.getLong(1); }
                }
                ProjectMapper projectMapper = session.getMapper(ProjectMapper.class);
                ReportMapper reportMapper = session.getMapper(ReportMapper.class);
                ProjectReviewMapper reviewMapper = session.getMapper(ProjectReviewMapper.class);
                AuditLogService audit = mock(AuditLogService.class);
                ProjectReviewService service = new ProjectReviewService(projectMapper, reviewMapper, reportMapper, audit, new ObjectMapper());
                ProjectReviewRun run = service.run(workspace, project, reportId, user);
                assertNotNull(run.getCreatedAt()); assertEquals(reportId, run.getReportId()); assertEquals(10, run.getChecks().size());
                assertEquals(0, run.getBlockedCount()); assertTrue(service.policy(workspace, project, user).isCanManage());
                List<String> confirmations = run.getChecks().stream().filter(check -> check.status().equals("REVIEW")).map(ProjectReviewCheck::key).toList();
                ProjectReviewRun approved = service.decide(workspace, project, run.getId(), user, "APPROVED", "已核验原文、数字及适用条件。", confirmations);
                assertNotNull(approved.getDecidedAt()); assertNotNull(approved.getDecidedByName()); assertEquals(confirmations, approved.getConfirmations());
                assertEquals("已核验原文、数字及适用条件。", service.history(workspace, project, user).getFirst().getDecisionComment());
                assertFalse(service.history(workspace, project, user).getFirst().isStale());
                var principal = new UserLoginByPassword(); principal.setId(user);
                var auth = new UsernamePasswordAuthenticationToken(principal, null, List.of());
                ReportController controller = new ReportController(reportMapper, mock(NotificationService.class), audit, service);
                controller.update(workspace, project, reportId, Map.of("status", "PUBLISHED"), auth);
                assertEquals("PUBLISHED", reportMapper.findById(reportId, project, user).getStatus());
                controller.update(workspace, project, reportId, Map.of("content", "修订后的住宿上限为900元 [E1]。"), auth);
                assertEquals("DRAFT", reportMapper.findById(reportId, project, user).getStatus());
                assertTrue(service.history(workspace, project, user).getFirst().isStale());
                assertEquals("住宿上限为800元 [E1]，条件须核对。", service.history(workspace, project, user).getFirst().getReportSnapshot().get("content"));
                long finalWorkspace = workspace, finalProject = project, finalReport = reportId, finalUser = user;
                assertEquals("REPORT_REVIEW_STALE", assertThrows(ApiException.class, () -> controller.update(finalWorkspace, finalProject, finalReport, Map.of("status", "PUBLISHED"), auth)).getCode());
                ProjectReviewRun second = service.run(workspace, project, reportId, user);
                service.decide(workspace, project, second.getId(), user, "CHANGES_REQUESTED", "请核实900元的适用时间。", List.of());
                assertEquals(2, service.history(workspace, project, user).size());
                assertEquals("CHANGES_REQUESTED", service.latest(workspace, project, reportId, user).getStatus());
                assertEquals("PROJECT_NOT_FOUND", assertThrows(ApiException.class, () -> service.history(-1L, finalProject, finalUser)).getCode());
            } finally { session.rollback(true); }
        }
    }
}
