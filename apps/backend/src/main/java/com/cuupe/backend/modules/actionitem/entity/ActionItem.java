package com.cuupe.backend.modules.actionitem.entity;

import lombok.Data;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ActionItem {
    private Long id;
    private Long projectId;
    private Long createdBy;
    private String title;
    private String description;
    private Long ownerId;
    private String owner;
    private LocalDate dueAt;
    private String priority;
    private String status;
    private Long sourceReportId;
    private String sourceReportTitle;
    private String sourceReportVersion;
    private Long sourceReviewRunId;
    private String sourceKey;
    private String sourceExcerpt;
    private String acceptanceCriteria;
    private Boolean blocksRelease;
    private String completionEvidence;
    private Long submittedBy;
    private LocalDateTime submittedAt;
    private Long acceptedBy;
    private String acceptedByName;
    private LocalDateTime acceptedAt;
    private String acceptanceComment;
    private boolean canManage;
    private boolean canEdit;
    private boolean canAccept;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
