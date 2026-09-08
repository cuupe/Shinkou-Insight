package com.cuupe.backend.modules.security.entity;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class SecurityHarnessResult {
    private Long id;
    private Long runId;
    private String caseCode;
    private String name;
    private String category;
    private String severity;
    private String status;
    private String message;
    private String evidence;
    private LocalDateTime createdAt;
}
