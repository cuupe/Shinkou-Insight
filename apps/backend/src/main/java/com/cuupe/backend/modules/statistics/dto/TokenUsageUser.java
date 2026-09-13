package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;

@Data
public class TokenUsageUser {
    private Long userId;
    private String userName;
    private Long totalTokens;
    private Long runCount;
}
