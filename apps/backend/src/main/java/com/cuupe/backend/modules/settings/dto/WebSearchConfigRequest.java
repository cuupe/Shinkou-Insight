package com.cuupe.backend.modules.settings.dto;

import jakarta.validation.constraints.NotBlank;

public record WebSearchConfigRequest(
        String provider,
        @NotBlank String baseUrl,
        String apiKey,
        String language,
        Boolean enabled
) {}
