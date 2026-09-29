package com.cuupe.backend.modules.research.mapper;
import com.cuupe.backend.modules.research.entity.ResearchRun; import org.apache.ibatis.annotations.*; import java.util.List;
@Mapper public interface ResearchRunMapper {
    List<ResearchRun> findByProject(@Param("projectId") Long projectId,@Param("userId") Long userId);
    ResearchRun findById(@Param("id") Long id,@Param("projectId") Long projectId,@Param("userId") Long userId);
    int insert(ResearchRun run);
    int updateStatus(@Param("id") Long id,@Param("projectId") Long projectId,@Param("userId") Long userId,@Param("status") String status);
    int updateRuntime(@Param("id") Long id, @Param("projectId") Long projectId, @Param("userId") Long userId,
                      @Param("status") String status, @Param("progress") Integer progress,
                      @Param("currentStep") String currentStep, @Param("errorMessage") String errorMessage,
                      @Param("durationSeconds") Integer durationSeconds);
    int insertReport(@Param("id") Long id, @Param("projectId") Long projectId, @Param("userId") Long userId,
                     @Param("title") String title, @Param("summary") String summary,
                     @Param("recommendation") String recommendation, @Param("content") String content,
                     @Param("citations") int citations);
}
