package com.cuupe.backend.modules.project.mapper;

import com.cuupe.backend.modules.project.entity.ProjectReviewPolicy;
import com.cuupe.backend.modules.project.entity.ProjectReviewRun;
import org.apache.ibatis.annotations.*;
import java.util.List;
import java.util.Map;

@Mapper
public interface ProjectReviewMapper {
    @Select("""
        SELECT id,title,status,source_key AS "sourceKey",blocks_release AS "blocksRelease",
               acceptance_criteria AS "acceptanceCriteria",completion_evidence AS "completionEvidence",
               accepted_by AS "acceptedBy",accepted_at::text AS "acceptedAt",updated_at::text AS "updatedAt"
        FROM action_items WHERE project_id=#{projectId} AND source_report_id=#{reportId} ORDER BY id
        """)
    List<Map<String,Object>> actionSnapshot(@Param("projectId") Long projectId,@Param("reportId") Long reportId);

    @Select("SELECT id FROM projects WHERE workspace_id=#{workspaceId} AND id=#{projectId} FOR UPDATE")
    Long lockProject(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId);

    @Select("""
        SELECT id, name, index_status AS "indexStatus", updated_at::text AS "updatedAt"
        FROM knowledge_assets WHERE project_id=#{projectId} ORDER BY id
        """)
    List<Map<String, Object>> assetSnapshot(@Param("projectId") Long projectId);

    @Select("""
        SELECT id, status, evaluation_result->>'status' AS "retrievalStatus", updated_at::text AS "updatedAt"
        FROM evaluation_cases WHERE project_id=#{projectId} ORDER BY id
        """)
    List<Map<String, Object>> evaluationSnapshot(@Param("projectId") Long projectId);

    @Select("""
        SELECT id, status, updated_at::text AS "updatedAt" FROM research_runs
        WHERE project_id=#{projectId} AND id=#{runId}
        """)
    Map<String, Object> researchSnapshot(@Param("projectId") Long projectId, @Param("runId") Long runId);

    @Select("""
        SELECT project_id AS projectId, workspace_id AS workspaceId,
               require_citations AS requireCitations, verify_numbers AS verifyNumbers,
               escalate_conflicts AS escalateConflicts, label_external AS labelExternal,
               updated_by AS updatedBy, created_at AS createdAt, updated_at AS updatedAt
        FROM project_review_policies
        WHERE workspace_id = #{workspaceId} AND project_id = #{projectId}
        """)
    ProjectReviewPolicy findPolicy(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId);

    @Insert("""
        INSERT INTO project_review_policies
            (project_id, workspace_id, require_citations, verify_numbers,
             escalate_conflicts, label_external, updated_by)
        VALUES
            (#{projectId}, #{workspaceId}, #{requireCitations}, #{verifyNumbers},
             #{escalateConflicts}, #{labelExternal}, #{updatedBy})
        ON CONFLICT (project_id) DO UPDATE SET
            workspace_id = EXCLUDED.workspace_id,
            require_citations = EXCLUDED.require_citations,
            verify_numbers = EXCLUDED.verify_numbers,
            escalate_conflicts = EXCLUDED.escalate_conflicts,
            label_external = EXCLUDED.label_external,
            updated_by = EXCLUDED.updated_by,
            updated_at = CURRENT_TIMESTAMP
        """)
    int upsertPolicy(ProjectReviewPolicy policy);

    @Select("SELECT COUNT(*) FROM knowledge_assets WHERE project_id = #{projectId}")
    int countAssets(@Param("projectId") Long projectId);

    @Select("SELECT COUNT(*) FROM knowledge_assets WHERE project_id = #{projectId} AND index_status = 'SUCCESS'")
    int countIndexedAssets(@Param("projectId") Long projectId);

    @Select("SELECT COUNT(*) FROM research_runs WHERE project_id = #{projectId}")
    int countResearchRuns(@Param("projectId") Long projectId);

    @Select("SELECT COUNT(*) FROM reports WHERE project_id = #{projectId}")
    int countReports(@Param("projectId") Long projectId);

    @Select("SELECT COUNT(*) FROM evaluation_cases WHERE project_id = #{projectId}")
    int countEvaluationCases(@Param("projectId") Long projectId);

    @Select("SELECT COUNT(*) FROM action_items WHERE project_id = #{projectId}")
    int countActionItems(@Param("projectId") Long projectId);

    @Insert("""
        INSERT INTO project_review_runs
            (project_id, workspace_id, created_by, status, blocked_count, review_count,
             indexed_asset_count, asset_count, research_run_count, report_count,
             evaluation_case_count, action_item_count, require_citations, verify_numbers,
             escalate_conflicts, label_external, detail, report_id, report_title, report_version, snapshot_hash, checks, report_snapshot)
        VALUES
            (#{projectId}, #{workspaceId}, #{createdBy}, #{status}, #{blockedCount}, #{reviewCount},
             #{indexedAssetCount}, #{assetCount}, #{researchRunCount}, #{reportCount},
             #{evaluationCaseCount}, #{actionItemCount}, #{requireCitations}, #{verifyNumbers},
             #{escalateConflicts}, #{labelExternal}, #{detail}, #{reportId}, #{reportTitle}, #{reportVersion}, #{snapshotHash}, CAST(#{checksJson} AS jsonb), CAST(#{reportSnapshotJson} AS jsonb))
        """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insertRun(ProjectReviewRun run);

    @Select("""
        SELECT id, project_id AS projectId, workspace_id AS workspaceId, created_by AS createdBy,
               status, blocked_count AS blockedCount, review_count AS reviewCount,
               indexed_asset_count AS indexedAssetCount, asset_count AS assetCount,
               research_run_count AS researchRunCount, report_count AS reportCount,
               evaluation_case_count AS evaluationCaseCount, action_item_count AS actionItemCount,
               require_citations AS requireCitations, verify_numbers AS verifyNumbers,
               escalate_conflicts AS escalateConflicts, label_external AS labelExternal,
               detail, created_at AS createdAt
        FROM project_review_runs
        WHERE workspace_id = #{workspaceId} AND project_id = #{projectId}
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """)
    ProjectReviewRun findLatestRun(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId);

    String REVIEW_COLUMNS = "r.id,r.project_id,r.workspace_id,r.created_by,r.status,r.blocked_count,r.review_count," +
            "r.indexed_asset_count,r.asset_count,r.research_run_count,r.report_count,r.evaluation_case_count,r.action_item_count," +
            "r.require_citations,r.verify_numbers,r.escalate_conflicts,r.label_external,r.detail,r.created_at," +
            "r.report_id,r.report_title,r.report_version,r.snapshot_hash,r.decision_comment,r.decided_by,r.decided_at," +
            "r.checks::text AS checks_json,r.confirmations::text AS confirmations_json,r.report_snapshot::text AS report_snapshot_json,u.user_name AS decided_by_name";

    @Select("SELECT " + REVIEW_COLUMNS + " FROM project_review_runs r LEFT JOIN users u ON u.id=r.decided_by " +
            "WHERE r.workspace_id=#{workspaceId} AND r.project_id=#{projectId} ORDER BY r.id DESC LIMIT 50")
    List<ProjectReviewRun> findHistory(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId);

    @Select("SELECT " + REVIEW_COLUMNS + " FROM project_review_runs r LEFT JOIN users u ON u.id=r.decided_by " +
            "WHERE r.workspace_id=#{workspaceId} AND r.project_id=#{projectId} AND r.id=#{id}")
    ProjectReviewRun findRun(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("id") Long id);

    @Select("SELECT " + REVIEW_COLUMNS + " FROM project_review_runs r LEFT JOIN users u ON u.id=r.decided_by " +
            "WHERE r.workspace_id=#{workspaceId} AND r.project_id=#{projectId} AND r.report_id=#{reportId} ORDER BY r.id DESC LIMIT 1")
    ProjectReviewRun findLatestForReport(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("reportId") Long reportId);

    @Update("""
        UPDATE project_review_runs SET status=#{status}, confirmations=CAST(#{confirmationsJson} AS jsonb),
            decision_comment=#{decisionComment}, decided_by=#{decidedBy}, decided_at=CURRENT_TIMESTAMP
        WHERE workspace_id=#{workspaceId} AND project_id=#{projectId} AND id=#{id} AND decided_at IS NULL
        """)
    int decide(ProjectReviewRun run);
}
