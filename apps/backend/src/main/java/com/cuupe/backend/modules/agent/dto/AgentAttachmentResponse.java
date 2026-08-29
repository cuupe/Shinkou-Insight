package com.cuupe.backend.modules.agent.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class AgentAttachmentResponse {
    private Long uploadId;
    private String name;
    private String kind;
    private String mimeType;
    private Long size;
    private String url;
}
