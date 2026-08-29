package com.cuupe.backend.modules.actionitem.entity;

import lombok.Data;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ActionItem {
    private Long id;
    private Long projectId;
    private Long createdBy;
    private String title;
    private String description;
    private Long ownerId;
    private String owner;
    private LocalDate dueAt;
    private String priority;
    private String status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}