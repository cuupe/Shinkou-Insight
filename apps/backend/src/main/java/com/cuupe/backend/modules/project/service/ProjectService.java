package com.cuupe.backend.modules.project.service;

import com.cuupe.backend.modules.project.dto.ProjectRequest;
import com.cuupe.backend.modules.project.dto.ChunkingConfigRequest;
import com.cuupe.backend.modules.project.entity.Project;
import java.util.List;

public interface ProjectService {
    List<Project> list(Long workspaceId, Long userId);
    Project detail(Long workspaceId, Long projectId, Long userId);
    Project create(Long workspaceId, Long userId, ProjectRequest request);
    Project update(Long workspaceId, Long projectId, Long userId, ProjectRequest request);
    Project updateChunking(Long workspaceId, Long projectId, Long userId, ChunkingConfigRequest request);
    void delete(Long workspaceId, Long projectId, Long userId);
    Project changeStatus(Long workspaceId, Long projectId, Long userId, String status);
}
