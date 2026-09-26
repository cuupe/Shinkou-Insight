package com.cuupe.backend.modules.agent.mapper;

import com.cuupe.backend.modules.agent.entity.AgentAttachment;
import com.cuupe.backend.modules.agent.entity.AgentMessage;
import com.cuupe.backend.modules.agent.entity.AgentRun;
import com.cuupe.backend.modules.agent.entity.AgentRunEvent;
import com.cuupe.backend.modules.agent.entity.AgentTokenUsage;
import com.cuupe.backend.modules.agent.entity.AgentThread;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface AgentMapper {
    boolean hasProjectAccess(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    AgentThread findThread(@Param("threadKey") String threadKey, @Param("projectId") Long projectId, @Param("userId") Long userId);
    List<AgentThread> findThreads(@Param("projectId") Long projectId, @Param("userId") Long userId);
    int insertThread(AgentThread thread);
    int touchThread(@Param("id") Long id, @Param("title") String title);
    boolean hasRunningRun(@Param("threadId") Long threadId);
    int deleteThread(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int insertMessage(AgentMessage message);
    List<AgentMessage> findMessages(@Param("threadId") Long threadId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    AgentMessage findFirstUserMessage(@Param("threadId") Long threadId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    String findMessageKey(@Param("id") Long id);
    String findMessageAttachments(@Param("id") Long id);
    int updateMessage(@Param("id") Long id, @Param("content") String content, @Param("status") String status);
    int updateMessageAttachments(@Param("id") Long id, @Param("attachments") String attachments);
    int insertRun(AgentRun run);
    List<AgentRun> findRunsByThread(@Param("threadId") Long threadId);
    AgentTokenUsage findTokenUsage(@Param("runKey") String runKey);
    AgentRun findRun(@Param("runKey") String runKey, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int updateRun(@Param("id") Long id, @Param("status") String status, @Param("errorMessage") String errorMessage);
    int insertEvent(AgentRunEvent event);
    int upsertTokenUsage(AgentTokenUsage usage);
    List<AgentRunEvent> findEvents(@Param("runKey") String runKey, @Param("afterId") Long afterId);
    int insertAttachment(AgentAttachment attachment);
    List<AgentAttachment> findAttachments(@Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    boolean hasAttachmentAccess(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    AgentAttachment findAttachment(@Param("id") Long id, @Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    AgentAttachment findAttachmentByStorageKey(@Param("storageKey") String storageKey, @Param("workspaceId") Long workspaceId, @Param("projectId") Long projectId, @Param("userId") Long userId);
}
