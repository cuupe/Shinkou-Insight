package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;

@Data
public class TokenUsageTrendPoint {
    private String date;
    private Long tokens;
    private Long runs;
}
