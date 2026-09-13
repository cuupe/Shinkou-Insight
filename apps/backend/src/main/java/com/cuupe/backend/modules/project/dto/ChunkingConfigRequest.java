package com.cuupe.backend.modules.project.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record ChunkingConfigRequest(
        String strategy,
        @Min(value = 400, message = "分块长度不能小于 400")
        @Max(value = 4000, message = "分块长度不能大于 4000")
        Integer chunkSize,
        @Min(value = 0, message = "重叠长度不能小于 0")
        @Max(value = 1200, message = "重叠长度不能大于 1200")
        Integer chunkOverlap,
        Boolean preserveSections
) {}
