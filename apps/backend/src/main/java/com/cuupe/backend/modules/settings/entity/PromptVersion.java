package com.cuupe.backend.modules.settings.entity;
import lombok.Data; import java.time.LocalDateTime;
@Data public class PromptVersion { private Long id; private Long workspaceId; private Long createdBy; private String scene; private String versionNo; private String systemPrompt; private String status; private LocalDateTime updatedAt; }