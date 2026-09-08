package com.cuupe.backend.modules.security.entity;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class SecurityHarnessRun {
    private Long id;
    private Long workspaceId;
    private Long projectId;
    private Long createdBy;
    private String status;
    private String mode;
    private Integer totalCases;
    private Integer passedCases;
    private Integer failedCases;
    private Integer blockedCases;
    private Double score;
    private String errorMessage;
    private LocalDateTime startedAt;
    private LocalDateTime finishedAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
