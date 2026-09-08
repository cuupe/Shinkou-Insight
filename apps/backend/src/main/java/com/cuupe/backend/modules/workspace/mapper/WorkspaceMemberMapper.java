package com.cuupe.backend.modules.workspace.mapper;
import com.cuupe.backend.modules.workspace.entity.WorkspaceInvitation;
import com.cuupe.backend.modules.workspace.entity.WorkspaceMember;
import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper public interface WorkspaceMemberMapper {
    List<WorkspaceMember> findAccessible(@Param("workspaceId") Long workspaceId,@Param("userId") Long userId);
    int updateRole(@Param("workspaceId") Long workspaceId,@Param("memberId") Long memberId,@Param("role") String role,@Param("userId") Long userId);
    int insertMember(@Param("workspaceId") Long workspaceId,@Param("userId") Long userId,@Param("role") String role);
    int insertInvitation(@Param("workspaceId") Long workspaceId,@Param("phoneNumber") String phoneNumber,@Param("department") String department,@Param("title") String title,@Param("inviteNote") String inviteNote,@Param("role") String role,@Param("tokenHash") String tokenHash,@Param("userId") Long userId);
    List<WorkspaceInvitation> findPendingInvitations(@Param("phoneNumber") String phoneNumber);
    WorkspaceInvitation findPendingInvitation(@Param("id") Long id, @Param("phoneNumber") String phoneNumber);
    int acceptInvitation(@Param("id") Long id, @Param("phoneNumber") String phoneNumber, @Param("userId") Long userId);
    int declineInvitation(@Param("id") Long id, @Param("phoneNumber") String phoneNumber);
    int revokeInvitation(@Param("workspaceId") Long workspaceId, @Param("invitationId") Long invitationId, @Param("userId") Long userId);
}
