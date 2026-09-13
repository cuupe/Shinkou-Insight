package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;

@Data
public class TokenUsageSummary {
    private Long totalTokens;
    private Long inputTokens;
    private Long outputTokens;
    private Long compressedContextTokens;
    private Long runCount;
}
