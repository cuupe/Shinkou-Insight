package com.cuupe.backend.modules.asset.entity;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class KnowledgeAsset {
    private Long id;
    private Long projectId;
    private String name;
    private String assetType;
    private String mimeType;
    private String language;
    private Long fileSize;
    private String checksum;
    private String storageKey;
    private String content;
    private String parseStatus;
    private String indexStatus;
    private Integer chunkCount;
    private Integer progress;
    private String errorMessage;
    private Long createdBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
