package com.cuupe.backend.modules.statistics.dto;

import lombok.Data;

@Data
public class StatisticsSummary {
    private Long projectCount;
    private Long activeProjectCount;
    private Long assetCount;
    private Long indexedAssetCount;
    private Long failedAssetCount;
    private Long chunkCount;
    private Long runCount;
    private Long queuedRunCount;
    private Long runningRunCount;
    private Long completedRunCount;
    private Long failedRunCount;
    private Long cancelledRunCount;
    private Long reportCount;
    private Long publishedReportCount;
    private Long actionItemCount;
    private Long openActionItemCount;
    private Long overdueActionItemCount;
    private Long evaluationCaseCount;
    private Double avgRecall;
    private Double avgCitation;
    private Double avgJsonScore;
    private Long unreadNotificationCount;
}
