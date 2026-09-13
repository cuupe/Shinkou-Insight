package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

@Data
public class AgentTokenUsage {
    private Long id;
    private Long workspaceId;
    private Long projectId;
    private Long userId;
    private Long runId;
    private String runKey;
    private String modelName;
    private Integer inputTokens;
    private Integer outputTokens;
    private Integer totalTokens;
    private Integer compressedContextTokens;
    private Integer contextMessageCount;
}
