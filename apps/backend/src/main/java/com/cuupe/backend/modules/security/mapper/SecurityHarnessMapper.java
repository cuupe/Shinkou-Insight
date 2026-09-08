package com.cuupe.backend.modules.security.mapper;

import com.cuupe.backend.modules.security.entity.SecurityHarnessResult;
import com.cuupe.backend.modules.security.entity.SecurityHarnessRun;
import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper
public interface SecurityHarnessMapper {
    @Insert("""
        INSERT INTO security_harness_runs(workspace_id, project_id, created_by, status, mode)
        VALUES(#{workspaceId}, #{projectId}, #{createdBy}, #{status}, #{mode})
        """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insertRun(SecurityHarnessRun run);

    @Select("""
        SELECT id, workspace_id AS workspaceId, project_id AS projectId, created_by AS createdBy,
               status, mode, total_cases AS totalCases, passed_cases AS passedCases,
               failed_cases AS failedCases, blocked_cases AS blockedCases, score,
               error_message AS errorMessage, started_at AS startedAt, finished_at AS finishedAt,
               created_at AS createdAt, updated_at AS updatedAt
        FROM security_harness_runs WHERE id = #{id} AND workspace_id = #{workspaceId}
        """)
    SecurityHarnessRun findRun(@Param("id") Long id, @Param("workspaceId") Long workspaceId);

    @Select("""
        SELECT id, run_id AS runId, case_code AS caseCode, name, category, severity, status,
               message, evidence::text AS evidence, created_at AS createdAt
        FROM security_harness_results WHERE run_id = #{runId} ORDER BY id
        """)
    List<SecurityHarnessResult> findResults(@Param("runId") Long runId);

    @Select("""
        SELECT id, workspace_id AS workspaceId, project_id AS projectId, created_by AS createdBy,
               status, mode, total_cases AS totalCases, passed_cases AS passedCases,
               failed_cases AS failedCases, blocked_cases AS blockedCases, score,
               error_message AS errorMessage, started_at AS startedAt, finished_at AS finishedAt,
               created_at AS createdAt, updated_at AS updatedAt
        FROM security_harness_runs WHERE workspace_id = #{workspaceId}
        ORDER BY created_at DESC LIMIT #{limit}
        """)
    List<SecurityHarnessRun> listRuns(@Param("workspaceId") Long workspaceId, @Param("limit") int limit);

    @Update("""
        UPDATE security_harness_runs SET status = #{status}, total_cases = #{totalCases},
          passed_cases = #{passedCases}, failed_cases = #{failedCases}, blocked_cases = #{blockedCases},
          score = #{score}, error_message = #{errorMessage}, finished_at = CURRENT_TIMESTAMP,
          updated_at = CURRENT_TIMESTAMP WHERE id = #{id} AND workspace_id = #{workspaceId}
        """)
    int finishRun(SecurityHarnessRun run);

    @Insert("""
        INSERT INTO security_harness_results(run_id, case_code, name, category, severity, status, message, evidence)
        VALUES(#{runId}, #{caseCode}, #{name}, #{category}, #{severity}, #{status}, #{message}, CAST(#{evidence} AS jsonb))
        """)
    int insertResult(SecurityHarnessResult result);
}
