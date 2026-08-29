package com.cuupe.backend.modules.agent.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class AgentRunAccepted {
    private String runId;
    private String messageId;
    private String status;
    private String eventsUrl;
}
