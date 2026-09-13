package com.cuupe.backend.modules.project.mapper;

import com.cuupe.backend.modules.project.entity.ProjectReviewPolicy;
import com.cuupe.backend.modules.project.entity.ProjectReviewRun;
import org.apache.ibatis.annotations.*;

@Mapper
public interface ProjectReviewMapper {
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
             escalate_conflicts, label_external, detail)
        VALUES
            (#{projectId}, #{workspaceId}, #{createdBy}, #{status}, #{blockedCount}, #{reviewCount},
             #{indexedAssetCount}, #{assetCount}, #{researchRunCount}, #{reportCount},
             #{evaluationCaseCount}, #{actionItemCount}, #{requireCitations}, #{verifyNumbers},
             #{escalateConflicts}, #{labelExternal}, #{detail})
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
}
