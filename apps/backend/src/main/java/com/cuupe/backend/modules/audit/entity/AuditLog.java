package com.cuupe.backend.modules.audit.entity;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class AuditLog {
    private Long id;
    private Long workspaceId;
    private Long projectId;
    private Long actorUserId;
    private String action;
    private String resourceType;
    private String resourceId;
    private String outcome;
    private String details;
    private LocalDateTime createdAt;
}
