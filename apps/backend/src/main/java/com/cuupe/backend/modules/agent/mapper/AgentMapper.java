package com.cuupe.backend.modules.agent.mapper;

import com.cuupe.backend.modules.agent.entity.AgentAttachment;
import com.cuupe.backend.modules.agent.entity.AgentMessage;
import com.cuupe.backend.modules.agent.entity.AgentRun;
import com.cuupe.backend.modules.agent.entity.AgentRunEvent;
import com.cuupe.backend.modules.agent.entity.AgentThread;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface AgentMapper {
    boolean hasProjectAccess(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    AgentThread findThread(@Param("threadKey") String threadKey, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int insertThread(AgentThread thread);
    int touchThread(@Param("id") Long id, @Param("title") String title);
    int insertMessage(AgentMessage message);
    String findMessageKey(@Param("id") Long id);
    int updateMessage(@Param("id") Long id, @Param("content") String content, @Param("status") String status);
    int insertRun(AgentRun run);
    AgentRun findRun(@Param("runKey") String runKey, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int updateRun(@Param("id") Long id, @Param("status") String status, @Param("errorMessage") String errorMessage);
    int insertEvent(AgentRunEvent event);
    List<AgentRunEvent> findEvents(@Param("runKey") String runKey, @Param("afterId") Long afterId);
    int insertAttachment(AgentAttachment attachment);
    boolean hasAttachmentAccess(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    AgentAttachment findAttachment(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
}
