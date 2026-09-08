package com.cuupe.backend.modules.project.mapper;

import com.cuupe.backend.modules.project.entity.Project;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import java.util.List;

@Mapper
public interface ProjectMapper {
    List<Project> findAccessible(@Param("workspaceId") Long workspaceId, @Param("userId") Long userId);
    Project findAccessibleById(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    Long findCreatorId(@Param("projectId") Long projectId);
    boolean hasWriteAccess(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int existsCode(@Param("workspaceId") Long workspaceId, @Param("code") String code, @Param("projectId") Long projectId);
    int insert(Project project);
    int update(Project project);
    int changeStatus(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("status") String status, @Param("userId") Long userId);
}
