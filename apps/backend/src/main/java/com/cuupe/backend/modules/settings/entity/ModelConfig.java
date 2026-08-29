package com.cuupe.backend.modules.settings.entity;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;
import java.time.LocalDateTime;
@Data public class ModelConfig { private Long id; private Long projectId; private String name; private String provider; private String modelId; private String endpoint; private String authType; @JsonIgnore private String credentialCiphertext; private boolean hasCredential; private String config; private boolean enabled; private Long createdBy; private LocalDateTime createdAt; private LocalDateTime updatedAt; }