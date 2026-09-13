package com.cuupe.backend.modules.settings.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.time.LocalDateTime;

/** 独立的联网搜索配置，不属于通用工具/连接器。 */
@Data
public class WebSearchConfig {
    private Long id;
    private Long projectId;
    private String provider;
    private String baseUrl;
    private String language;
    @JsonIgnore
    private String credentialCiphertext;
    private boolean hasCredential;
    private boolean enabled;
    private Long createdBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
