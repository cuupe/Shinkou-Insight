package com.cuupe.backend.modules.evaluation.entity;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class EvaluationCase {
    private Long id;
    private Long workspaceId;
    private Long projectId;
    private Long createdBy;
    private String query;
    private String expectedAnswer;
    private String expectedAsset;
    private String expectedChunkIds;
    private String requiredFacts;
    private String forbiddenFacts;
    private String evaluationResult;
    private LocalDateTime evaluatedAt;
    private Double recall;
    private Double citation;
    private Double jsonScore;
    private String status;
    private LocalDateTime updatedAt;
}
