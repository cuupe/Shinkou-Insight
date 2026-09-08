package com.cuupe.backend.modules.settings.entity;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;
import java.time.LocalDateTime;
@Data public class ToolConfig { private Long id; private Long projectId; private String name; private String connectorType; private String endpoint; private String authType; @JsonIgnore private String credentialCiphertext; private boolean hasCredential; private String config; private boolean enabled; private String scope; private Long createdBy; private LocalDateTime createdAt; private LocalDateTime updatedAt; }
