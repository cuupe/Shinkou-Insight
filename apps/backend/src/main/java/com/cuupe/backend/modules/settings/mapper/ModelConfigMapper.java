package com.cuupe.backend.modules.settings.mapper;
import com.cuupe.backend.modules.settings.entity.ModelConfig;
import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper
public interface ModelConfigMapper {
    List<ModelConfig> findForManagement(@Param("workspaceId") Long workspaceId, @Param("userId") Long userId);
    List<ModelConfig> findForProject(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId,
                                     @Param("creatorId") Long creatorId, @Param("userId") Long userId);
    ModelConfig findProjectVisibleById(@Param("id") Long id, @Param("workspaceId") Long workspaceId,
                                       @Param("projectId") Long projectId, @Param("creatorId") Long creatorId,
                                       @Param("userId") Long userId);
    List<ModelConfig> findForRuntime(@Param("workspaceId") Long workspaceId, @Param("creatorId") Long creatorId,
                                     @Param("userId") Long userId);
    ModelConfig findVisibleById(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("userId") Long userId);
    ModelConfig findOwnedById(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("userId") Long userId);
    int insert(ModelConfig config);
    int update(ModelConfig config);
    int delete(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("userId") Long userId);
    int clearDefault(@Param("workspaceId") Long workspaceId);
    int setDefault(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("userId") Long userId);
}
