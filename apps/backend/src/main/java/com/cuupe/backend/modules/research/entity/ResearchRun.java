package com.cuupe.backend.modules.research.entity;
import lombok.Data;
import java.time.LocalDateTime;
@Data public class ResearchRun { private Long id; private Long projectId; private Long createdBy; private String title; private String goal; private String status; private String priority; private String config; private String errorMessage; private Integer progress; private String currentStep; private Integer durationSeconds; private Long tokenCount; private String duration; private String tokens; private LocalDateTime createdAt; private LocalDateTime updatedAt; }
