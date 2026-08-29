package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.NotNull;

public record UpdatePreferencesRequest(
        @NotNull(message = "运行通知偏好不能为空") Boolean activity,
        @NotNull(message = "周报偏好不能为空") Boolean weeklyDigest
) {}