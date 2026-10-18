package com.cuupe.backend.modules.project.entity;

import lombok.Data;
import com.fasterxml.jackson.annotation.JsonIgnore;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

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
    private Long reportId;
    private String reportTitle;
    private String reportVersion;
    @JsonIgnore private String snapshotHash;
    @JsonIgnore private String checksJson;
    @JsonIgnore private String confirmationsJson;
    @JsonIgnore private String reportSnapshotJson;
    private Map<String, Object> reportSnapshot = Map.of();
    private List<ProjectReviewCheck> checks = List.of();
    private List<String> confirmations = List.of();
    private String decisionComment;
    private Long decidedBy;
    private String decidedByName;
    private LocalDateTime decidedAt;
    private boolean stale;
}
