package com.cuupe.backend.modules.auth.dto.response;

public record LoginResponse(
        Long id,
        String phoneNumber,
        String userName
) {
}
