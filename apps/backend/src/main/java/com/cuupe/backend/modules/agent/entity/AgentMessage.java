package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

@Data
public class AgentMessage {
    private Long id;
    private Long threadId;
    private String clientMessageId;
    private String role;
    private String content;
    private String status;
    private String attachments;
}
