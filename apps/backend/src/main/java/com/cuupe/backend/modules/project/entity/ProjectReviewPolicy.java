package com.cuupe.backend.modules.project.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ProjectReviewPolicy {
    private Long projectId;
    private Long workspaceId;
    private boolean requireCitations = true;
    private boolean verifyNumbers = true;
    private boolean escalateConflicts = true;
    private boolean labelExternal = true;
    private Long updatedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
