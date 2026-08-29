package com.cuupe.backend.modules.report.entity;
import lombok.Data; import java.time.LocalDateTime;
@Data public class Report { private Long id; private Long projectId; private Long runId; private String title; private String status; private String versionNo; private String lead; private String summary; private String recommendation; private String recommendationDetail; private Integer citations; private String content; private Long createdBy; private LocalDateTime createdAt; private LocalDateTime updatedAt; }
