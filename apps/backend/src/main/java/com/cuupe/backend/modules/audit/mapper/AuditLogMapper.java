package com.cuupe.backend.modules.audit.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import com.cuupe.backend.modules.audit.entity.AuditLog;
import java.util.List;

@Mapper
public interface AuditLogMapper {
    @Select("""
            SELECT id, workspace_id AS workspaceId, project_id AS projectId, actor_user_id AS actorUserId,
                   action, resource_type AS resourceType, resource_id AS resourceId, outcome,
                   details::text AS details, created_at AS createdAt
            FROM audit_logs WHERE workspace_id = #{workspaceId}
            ORDER BY created_at DESC LIMIT #{limit}
            """)
    List<AuditLog> findByWorkspace(@Param("workspaceId") Long workspaceId, @Param("limit") int limit);

    @Insert("""
            INSERT INTO audit_logs(
                workspace_id, project_id, actor_user_id, action,
                resource_type, resource_id, outcome, details
            ) VALUES(
                #{workspaceId}, #{projectId}, #{actorUserId}, #{action},
                #{resourceType}, #{resourceId}, #{outcome}, CAST(#{details} AS jsonb)
            )
            """)
    int insert(
            @Param("workspaceId") Long workspaceId,
            @Param("projectId") Long projectId,
            @Param("actorUserId") Long actorUserId,
            @Param("action") String action,
            @Param("resourceType") String resourceType,
            @Param("resourceId") String resourceId,
            @Param("outcome") String outcome,
            @Param("details") String details
    );
}
