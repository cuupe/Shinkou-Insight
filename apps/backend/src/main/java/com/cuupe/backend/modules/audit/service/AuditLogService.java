package com.cuupe.backend.modules.audit.service;

import com.cuupe.backend.modules.audit.mapper.AuditLogMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

import java.util.Map;
import java.util.List;
import com.cuupe.backend.modules.audit.entity.AuditLog;

@Service
@RequiredArgsConstructor
public class AuditLogService {
    private final AuditLogMapper mapper;
    private final ObjectMapper objectMapper;

    public void record(
            Long workspaceId,
            Long projectId,
            Long actorUserId,
            String action,
            String resourceType,
            Object resourceId,
            Map<String, ?> details
    ) {
        String json;
        try {
            json = objectMapper.writeValueAsString(details == null ? Map.of() : details);
        } catch (Exception exception) {
            json = "{}";
        }
        mapper.insert(
                workspaceId,
                projectId,
                actorUserId,
                action,
                resourceType,
                resourceId == null ? null : String.valueOf(resourceId),
                "SUCCESS",
                json
        );
    }

    public void recordFailure(
            Long workspaceId,
            Long projectId,
            Long actorUserId,
            String action,
            String resourceType,
            Object resourceId,
            Map<String, ?> details
    ) {
        String json;
        try {
            json = objectMapper.writeValueAsString(details == null ? Map.of() : details);
        } catch (Exception exception) {
            json = "{}";
        }
        mapper.insert(
                workspaceId,
                projectId,
                actorUserId,
                action,
                resourceType,
                resourceId == null ? null : String.valueOf(resourceId),
                "FAILURE",
                json
        );
    }

    public void record(
            Long workspaceId,
            Long projectId,
            Long actorUserId,
            String action,
            String resourceType,
            Object resourceId
    ) {
        record(workspaceId, projectId, actorUserId, action, resourceType, resourceId, Map.of());
    }

    public List<AuditLog> list(Long workspaceId, int limit) {
        return mapper.findByWorkspace(workspaceId, Math.max(1, Math.min(limit, 200)));
    }
}
