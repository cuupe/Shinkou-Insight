package com.cuupe.backend.modules.statistics.mapper;

import com.cuupe.backend.modules.statistics.dto.StatisticsBreakdown;
import com.cuupe.backend.modules.statistics.dto.StatisticsSummary;
import com.cuupe.backend.modules.statistics.dto.StatisticsTrendPoint;
import com.cuupe.backend.modules.statistics.dto.TokenUsageSummary;
import com.cuupe.backend.modules.statistics.dto.TokenUsageTrendPoint;
import com.cuupe.backend.modules.statistics.dto.TokenUsageUser;
import com.cuupe.backend.modules.statistics.dto.TokenUsageBreakdown;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import java.util.List;

@Mapper
public interface StatisticsMapper {
    StatisticsSummary findSummary(@Param("workspaceId") Long workspaceId,
                                   @Param("projectId") Long projectId,
                                   @Param("userId") Long userId);

    List<StatisticsTrendPoint> findDailyTrend(@Param("workspaceId") Long workspaceId,
                                              @Param("projectId") Long projectId,
                                              @Param("userId") Long userId,
                                              @Param("days") int days);

    List<StatisticsBreakdown> findRunStatuses(@Param("workspaceId") Long workspaceId,
                                              @Param("projectId") Long projectId,
                                              @Param("userId") Long userId);

    List<StatisticsBreakdown> findAssetStatuses(@Param("workspaceId") Long workspaceId,
                                                @Param("projectId") Long projectId,
                                                @Param("userId") Long userId);

    List<StatisticsBreakdown> findActionItemStatuses(@Param("workspaceId") Long workspaceId,
                                                     @Param("projectId") Long projectId,
                                                     @Param("userId") Long userId);

    TokenUsageSummary findTokenUsageSummary(@Param("workspaceId") Long workspaceId,
                                            @Param("projectId") Long projectId,
                                            @Param("userId") Long userId);

    List<TokenUsageTrendPoint> findTokenUsageTrend(@Param("workspaceId") Long workspaceId,
                                                   @Param("projectId") Long projectId,
                                                   @Param("userId") Long userId,
                                                   @Param("days") int days);

    List<TokenUsageUser> findTokenUsageUsers(@Param("workspaceId") Long workspaceId,
                                             @Param("projectId") Long projectId,
                                             @Param("userId") Long userId);

    List<TokenUsageBreakdown> findTokenUsageBreakdown(@Param("workspaceId") Long workspaceId,
                                                      @Param("projectId") Long projectId,
                                                      @Param("userId") Long userId);
}
