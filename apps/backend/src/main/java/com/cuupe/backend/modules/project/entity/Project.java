package com.cuupe.backend.modules.project.entity;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class Project {
    private Long id;
    private Long workspaceId;
    private String code;
    private String name;
    private String description;
    private String color;
    private String visibility;
    private String status;
    private LocalDateTime archivedAt;
    private Long createdBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private Long assets;
    private Long runs;
    private Long reports;
}
