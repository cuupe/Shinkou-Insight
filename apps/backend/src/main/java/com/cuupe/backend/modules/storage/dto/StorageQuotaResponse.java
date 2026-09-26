package com.cuupe.backend.modules.storage.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class StorageQuotaResponse {
    private long fileBytes;
    private long knowledgeBytes;
    private long usedBytes;
    private long maxBytes;
    private long remainingBytes;
    private int usagePercent;
    private long maxSingleFileBytes;
}
