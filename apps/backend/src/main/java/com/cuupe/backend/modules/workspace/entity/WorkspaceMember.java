package com.cuupe.backend.modules.workspace.entity;
import lombok.Data; import java.time.LocalDateTime;
@Data public class WorkspaceMember { private Long id; private Long userId; private String userName; private String phoneNumber; private String department; private String title; private String role; private String status; private LocalDateTime createdAt; private LocalDateTime lastActiveAt; }
