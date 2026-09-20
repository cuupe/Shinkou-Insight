package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record LoginRequestBySms(
        @NotBlank(message = "手机号不能为空")
        @Pattern(regexp = "^1\\d{10}$", message = "请输入正确的11位手机号")
        String phoneNumber,
        @NotBlank(message = "手机验证码不能为空")
        @Pattern(regexp = "^\\d{6}$", message = "请输入6位手机验证码")
        String verifyCode,
        @NotBlank(message = "短信验证码ID不能为空")
        @Size(max = 100, message = "验证码ID格式不正确")
        String verifyCodeId,
        // 保留可选字段兼容旧客户端；短信登录流程不使用图片验证码。
        @Size(max = 8, message = "验证码格式不正确")
        String captcha,
        @Size(max = 100, message = "验证码格式不正确")
        String captchaId
) {
}
