package com.cuupe.backend.modules.settings.dto;
import jakarta.validation.constraints.NotBlank;
public record ToolConfigRequest(@NotBlank String name, @NotBlank String endpoint, String connectorType, String authType, String credential, String config, Boolean enabled) {}