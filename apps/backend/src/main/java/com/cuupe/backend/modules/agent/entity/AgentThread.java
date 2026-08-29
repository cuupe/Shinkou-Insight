package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AgentThread {
    private Long id;
    private Long workspaceId;
    private Long projectId;
    private Long createdBy;
    private String threadKey;
    private String title;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
