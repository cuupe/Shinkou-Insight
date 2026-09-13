package com.cuupe.backend.modules.project.mapper;

import com.cuupe.backend.modules.project.entity.ProjectPlan;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface ProjectPlanMapper {
    ProjectPlan findByProject(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId);
    int upsert(ProjectPlan plan);
}
