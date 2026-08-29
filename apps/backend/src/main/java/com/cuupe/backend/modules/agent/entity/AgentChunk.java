package com.cuupe.backend.modules.agent.entity;

import lombok.Data;

@Data
public class AgentChunk {
    private Long id;
    private Long assetId;
    private String assetName;
    private Integer pageNumber;
    private String content;
}
