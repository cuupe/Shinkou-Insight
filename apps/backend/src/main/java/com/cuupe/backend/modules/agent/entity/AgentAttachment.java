package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

@Data
public class AgentAttachment {
    private Long id;
    private Long workspaceId;
    private Long projectId;
    private Long uploadedBy;
    private String fileName;
    private String kind;
    private String mimeType;
    private Long fileSize;
    private String storageKey;
    private byte[] content;
}
