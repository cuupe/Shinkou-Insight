package com.cuupe.backend.modules.project.service.impl;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.project.dto.ProjectRequest;
import com.cuupe.backend.modules.project.dto.ChunkingConfigRequest;
import com.cuupe.backend.modules.project.entity.Project;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.project.service.ProjectService;
import tools.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ProjectServiceImpl implements ProjectService {
    private final ProjectMapper projectMapper;
    private final ObjectMapper objectMapper;

    @Override public List<Project> list(Long workspaceId, Long userId) { return projectMapper.findAccessible(workspaceId, userId); }

    @Override public Project detail(Long workspaceId, Long projectId, Long userId) { return required(workspaceId, projectId, userId); }

    @Override @Transactional
    public Project create(Long workspaceId, Long userId, ProjectRequest request) {
        String code = normalizeCode(request.code(), request.name());
        ensureCodeAvailable(workspaceId, code, null);
        Project project = new Project();
        project.setWorkspaceId(workspaceId);
        project.setCreatedBy(userId);
        project.setCode(code);
        project.setName(request.name().trim());
        project.setDescription(blankToNull(request.description()));
        project.setColor(normalizeColor(request.color()));
        project.setVisibility(normalizeVisibility(request.visibility()));
        projectMapper.insert(project);
        return required(workspaceId, project.getId(), userId);
    }

    @Override @Transactional
    public Project update(Long workspaceId, Long projectId, Long userId, ProjectRequest request) {
        Project project = required(workspaceId, projectId, userId);
        ensureWriteAccess(workspaceId, projectId, userId);
        if (request.name() != null && !request.name().isBlank()) project.setName(request.name().trim());
        if (request.description() != null) project.setDescription(blankToNull(request.description()));
        if (request.color() != null) project.setColor(normalizeColor(request.color()));
        if (request.visibility() != null) project.setVisibility(normalizeVisibility(request.visibility()));
        projectMapper.update(project);
        return required(workspaceId, projectId, userId);
    }

    @Override @Transactional
    public Project updateChunking(Long workspaceId, Long projectId, Long userId, ChunkingConfigRequest request) {
        Project project = required(workspaceId, projectId, userId);
        ensureWriteAccess(workspaceId, projectId, userId);
        String strategy = request.strategy() == null || request.strategy().isBlank()
                ? "natural" : request.strategy().trim().toLowerCase(Locale.ROOT);
        if (!strategy.equals("natural") && !strategy.equals("paragraph") && !strategy.equals("fixed")) {
            throw ApiException.badRequest("INVALID_CHUNKING_STRATEGY", "分块策略不正确");
        }
        int chunkSize = request.chunkSize() == null ? 1200 : request.chunkSize();
        int chunkOverlap = request.chunkOverlap() == null ? 180 : request.chunkOverlap();
        if (chunkOverlap >= chunkSize) throw ApiException.badRequest("INVALID_CHUNKING_OVERLAP", "重叠长度必须小于分块长度");
        boolean preserveSections = request.preserveSections() == null || request.preserveSections();
        try {
            String config = objectMapper.writeValueAsString(java.util.Map.of(
                    "strategy", strategy,
                    "chunkSize", chunkSize,
                    "chunkOverlap", chunkOverlap,
                    "preserveSections", preserveSections
            ));
            if (projectMapper.updateChunkingConfig(workspaceId, projectId, userId, config) == 0) throw notFound();
        } catch (ApiException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalStateException("分块配置保存失败", exception);
        }
        return required(workspaceId, projectId, userId);
    }

    @Override @Transactional
    public void delete(Long workspaceId, Long projectId, Long userId) {
        required(workspaceId, projectId, userId);
        ensureWriteAccess(workspaceId, projectId, userId);
        if (projectMapper.changeStatus(workspaceId, projectId, "DELETED", userId) == 0) throw notFound();
    }

    @Override @Transactional
    public Project changeStatus(Long workspaceId, Long projectId, Long userId, String status) {
        required(workspaceId, projectId, userId);
        ensureWriteAccess(workspaceId, projectId, userId);
        if (projectMapper.changeStatus(workspaceId, projectId, status, userId) == 0) throw notFound();
        return required(workspaceId, projectId, userId);
    }

    private Project required(Long workspaceId, Long projectId, Long userId) {
        Project project = projectMapper.findAccessibleById(workspaceId, projectId, userId);
        if (project == null) throw notFound();
        return project;
    }

    private void ensureWriteAccess(Long workspaceId, Long projectId, Long userId) {
        if (!projectMapper.hasWriteAccess(workspaceId, projectId, userId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "PROJECT_WRITE_FORBIDDEN", "只有项目创建者或管理员可以修改项目设置");
        }
    }

    private void ensureCodeAvailable(Long workspaceId, String code, Long projectId) {
        if (projectMapper.existsCode(workspaceId, code, projectId) > 0) throw ApiException.conflict("PROJECT_CODE_EXISTS", "项目编码已存在");
    }

    private String normalizeCode(String code, String name) {
        String value = code == null || code.isBlank() ? name : code;
        value = value.trim().toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "-").replaceAll("(^-|-$)", "");
        if (value.isBlank()) value = "project-" + UUID.randomUUID().toString().substring(0, 8);
        return value.length() > 80 ? value.substring(0, 80) : value;
    }

    private String normalizeVisibility(String visibility) {
        if (visibility == null || visibility.isBlank()) return "WORKSPACE";
        String value = visibility.trim().toUpperCase(Locale.ROOT);
        if (!value.equals("WORKSPACE") && !value.equals("PRIVATE")) throw ApiException.badRequest("INVALID_VISIBILITY", "项目可见范围不正确");
        return value;
    }

    private String blankToNull(String value) { return value == null || value.isBlank() ? null : value.trim(); }
    private String normalizeColor(String value) {
        if (value == null || value.isBlank()) return "#14b8a6";
        String color = value.trim();
        if (!color.matches("^#[0-9a-fA-F]{6}$")) throw ApiException.badRequest("INVALID_PROJECT_COLOR", "椤圭洰棰滆壊鏍煎紡涓嶆纭?");
        return color.toLowerCase(Locale.ROOT);
    }
    private ApiException notFound() { return new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问"); }
}
