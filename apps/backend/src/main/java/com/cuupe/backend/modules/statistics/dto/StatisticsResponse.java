package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;
import java.util.List;

@Data
public class StatisticsResponse {
    private StatisticsSummary summary;
    private List<StatisticsTrendPoint> dailyTrend;
    private List<StatisticsBreakdown> runStatuses;
    private List<StatisticsBreakdown> assetStatuses;
    private List<StatisticsBreakdown> actionItemStatuses;
}
