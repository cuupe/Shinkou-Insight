package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;

@Data
public class StatisticsTrendPoint {
    private String date;
    private Long assets;
    private Long runs;
    private Long reports;
    private Long actionItems;
    private Double recall;
    private Double citation;
    private Double jsonScore;
}
