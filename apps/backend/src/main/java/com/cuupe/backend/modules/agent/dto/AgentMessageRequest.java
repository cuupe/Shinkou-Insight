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
    private String modelName;
    private List<Map<String, Object>> attachments = new ArrayList<>();
    private Boolean allowWebSearch;
    private Boolean reflectionEnabled;
    private String strategy;
    private String multiAgentMode;
    private Integer maxResearchRounds;
    private Integer topK;
    private String retrievalMode;
    private Boolean useReranker;
    private String outputLanguage;
    private Double temperature;
    private Double topP;
    private Integer modelTopK;
    private Integer maxTokens;
    private Double frequencyPenalty;
    private String reasoningEffort;
    private Long modelConfigId;
    private List<Map<String, Object>> contextMessages = new ArrayList<>();
}
