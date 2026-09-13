package com.cuupe.backend.modules.project.entity;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ProjectPlan {
    private Long projectId;
    private Long workspaceId;
    private String objective;
    private String problem;
    private String successMetrics;
    private String constraints;
    private String owner;
    private LocalDate deadline;
    private Long updatedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
