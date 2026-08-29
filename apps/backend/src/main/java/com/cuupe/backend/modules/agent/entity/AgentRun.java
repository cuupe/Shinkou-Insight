package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AgentRun {
    private Long id;
    private String runKey;
    private Long threadId;
    private Long userMessageId;
    private Long assistantMessageId;
    private String status;
    private String errorMessage;
    private LocalDateTime startedAt;
    private LocalDateTime finishedAt;
    private LocalDateTime createdAt;
}
