package com.cuupe.backend.modules.project.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ProjectRequest(
        @NotBlank(message = "Project name is required")
        @Size(max = 120, message = "Project name is too long")
        String name,
        @Size(max = 80, message = "Project code is too long")
        String code,
        @Size(max = 500, message = "Project description is too long")
        String description,
        String visibility,
        @Size(max = 20, message = "Project color is too long")
        String color
) {}
