package com.cuupe.backend.modules.auth.dto.response;

public record CaptchaResponse(
        String captchaId,
        String imgUrl
) { }
