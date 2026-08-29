package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

@Data
public class AgentRunEvent {
    private Long id;
    private Long runId;
    private String eventType;
    private String payload;
}
