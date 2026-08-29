package com.cuupe.backend.modules.notification.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class Notification {
    private Long id;
    private Long workspaceId;
    private Long recipientUserId;
    private Long projectId;
    private String kind;
    private String title;
    private String body;
    private String routeName;
    private Boolean read;
    private LocalDateTime createdAt;
}
