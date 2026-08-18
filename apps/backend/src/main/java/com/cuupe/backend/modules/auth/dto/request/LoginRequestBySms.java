package com.cuupe.backend.modules.auth.dto.request;


import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record LoginRequestBySms(
        @NotBlank(message = "手机号不能为空")
        @Pattern(regexp = "^1\\d{10}$", message = "请输入正确的11位手机号")
        String phoneNumber,

        @NotBlank(message = "手机验证码不能为空")
        @Pattern(regexp = "^\\d{6}$", message = "请输入6位手机验证码")
        String verifyCode,

        @NotBlank(message = "短信验证码ID不能为空")
        String verifyCodeId,

        @NotBlank(message = "图片验证码不能为空")
        String captcha,

        @NotBlank(message = "图片验证码ID不能为空")
        String captchaId
) { }
