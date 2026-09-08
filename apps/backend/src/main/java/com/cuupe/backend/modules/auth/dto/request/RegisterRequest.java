package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record RegisterRequest(
        @NotBlank(message = "手机号不能为空")
        @Pattern(regexp = "^1\\d{10}$", message = "请输入正确的11位手机号")
        String phoneNumber,
        @NotBlank(message = "用户名不能为空")
        @Size(min = 2, max = 20, message = "用户名长度必须为2至20个字符")
        String userName,
        @NotBlank(message = "密码不能为空")
        @Size(min = 12, max = 72, message = "密码长度必须为12至72个字符")
        String password,
        @NotBlank(message = "图片验证码ID不能为空")
        @Size(max = 100, message = "验证码ID格式不正确")
        String captchaId,
        @NotBlank(message = "图片验证码不能为空")
        @Size(max = 8, message = "验证码格式不正确")
        String captcha,
        @NotBlank(message = "手机验证码ID不能为空")
        @Size(max = 100, message = "验证码ID格式不正确")
        String verifyCodeId,
        @NotBlank(message = "手机验证码不能为空")
        @Pattern(regexp = "^\\d{6}$", message = "请输入6位手机验证码")
        String verifyCode
) {
}
