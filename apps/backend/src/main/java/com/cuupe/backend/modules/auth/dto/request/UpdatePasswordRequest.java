package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdatePasswordRequest(
        @NotBlank(message = "当前密码不能为空") String currentPassword,
        @NotBlank(message = "新密码不能为空") @Size(min = 8, max = 72, message = "密码长度必须为 8 至 72 位") String newPassword,
        @NotBlank(message = "短信验证码ID不能为空") String verifyCodeId,
        @NotBlank(message = "短信验证码不能为空")
        @jakarta.validation.constraints.Pattern(regexp = "^\\d{6}$", message = "请输入6位手机验证码")
        String verifyCode
) {}
