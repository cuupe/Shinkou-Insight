package com.cuupe.backend.modules.project.dto;

import jakarta.validation.constraints.Size;

import java.time.LocalDate;

public record ProjectPlanRequest(
        @Size(max = 10000, message = "Project objective is too long") String objective,
        @Size(max = 10000, message = "Project problem is too long") String problem,
        @Size(max = 10000, message = "Success metrics are too long") String successMetrics,
        @Size(max = 10000, message = "Project constraints are too long") String constraints,
        @Size(max = 120, message = "Project owner is too long") String owner,
        LocalDate deadline
) {}
