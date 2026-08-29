package com.cuupe.backend.modules.settings.dto;
import jakarta.validation.constraints.NotBlank;
public record ModelConfigRequest(@NotBlank String name, @NotBlank String provider, @NotBlank String modelId, @NotBlank String endpoint, String authType, String credential, String config, Boolean enabled) {}