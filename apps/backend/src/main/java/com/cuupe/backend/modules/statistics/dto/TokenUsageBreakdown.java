package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;

@Data
public class TokenUsageBreakdown {
    private Long projectId;
    private String projectName;
    private Long userId;
    private String userName;
    private String modelName;
    private Long totalTokens;
    private Long inputTokens;
    private Long outputTokens;
    private Long runCount;
}
