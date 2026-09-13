package com.cuupe.backend.modules.project.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ProjectReviewRun {
    private Long id;
    private Long projectId;
    private Long workspaceId;
    private Long createdBy;
    private String status;
    private int blockedCount;
    private int reviewCount;
    private int indexedAssetCount;
    private int assetCount;
    private int researchRunCount;
    private int reportCount;
    private int evaluationCaseCount;
    private int actionItemCount;
    private boolean requireCitations;
    private boolean verifyNumbers;
    private boolean escalateConflicts;
    private boolean labelExternal;
    private String detail;
    private LocalDateTime createdAt;
}
