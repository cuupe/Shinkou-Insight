package com.cuupe.backend.modules.agent.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Data
public class AgentMessageRequest {
    private String threadId;
    private String messageId;
    private String content;
    private List<Map<String, Object>> attachments = new ArrayList<>();
}
