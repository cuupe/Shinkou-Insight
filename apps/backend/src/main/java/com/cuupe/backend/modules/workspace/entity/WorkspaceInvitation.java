package com.cuupe.backend.modules.workspace.entity;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class WorkspaceInvitation {
    private Long id;
    private Long workspaceId;
    private String workspaceName;
    private String phoneNumber;
    private String role;
    private String department;
    private String title;
    private String inviteNote;
    private Long invitedBy;
    private String status;
    private LocalDateTime expiresAt;
    private LocalDateTime createdAt;
}
