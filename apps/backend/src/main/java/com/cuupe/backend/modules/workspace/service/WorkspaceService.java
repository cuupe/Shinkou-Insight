package com.cuupe.backend.modules.workspace.service;

import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMapper;
import com.cuupe.backend.modules.workspace.mapper.WorkspaceMemberMapper;
import com.cuupe.backend.utils.SnowflakeIdGenerator;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 工作区创建服务：雪花 ID 生成 + 创建者自动成为 OWNER。
 */
@Service
@RequiredArgsConstructor
public class WorkspaceService {

    private final WorkspaceMapper workspaceMapper;
    private final WorkspaceMemberMapper memberMapper;

    @Transactional
    public Workspace create(String name, String code, String description, Long ownerId) {
        long id = SnowflakeIdGenerator.nextId();
        String workspaceCode = (code == null || code.isBlank())
                ? "ws-" + Long.toString(id, 36)
                : code.trim();
        workspaceMapper.insert(id, name.trim(), workspaceCode, description);
        memberMapper.insertMember(id, ownerId, "OWNER");
        return workspaceMapper.findById(id);
    }
}
