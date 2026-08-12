package com.cuupe.backend.modules.auth.dto.request;


import jakarta.validation.constraints.NotBlank;

public record RegisterRequest(
        @NotBlank(message = "手机号不能为空")
        String phoneNumber,

        @NotBlank(message = "用户名不能为空")
        String userName,

        @NotBlank(message = "密码不能为空")
        String password,

        @NotBlank(message = "图片验证码不能为空")
        String captcha,

        @NotBlank(message = "手机验证码不能为空")
        String verifyCode,

        @NotBlank(message = "图片验证码ID不能为空")
        String captchaId
) { }
