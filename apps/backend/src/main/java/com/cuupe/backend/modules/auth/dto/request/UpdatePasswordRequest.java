package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record UpdatePasswordRequest(
        @NotBlank(message = "当前密码不能为空") String currentPassword,
        @NotBlank(message = "新密码不能为空")
        @Size(min = 12, max = 72, message = "密码长度必须为12至72个字符") String newPassword,
        @NotBlank(message = "短信验证码ID不能为空")
        @Size(max = 100, message = "验证码ID格式不正确") String verifyCodeId,
        @NotBlank(message = "短信验证码不能为空")
        @Pattern(regexp = "^\\d{6}$", message = "请输入6位手机验证码") String verifyCode
) {
}
