package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record UpdatePhoneRequest(
        @NotBlank(message = "新手机号不能为空")
        @Pattern(regexp = "^1\\d{10}$", message = "请输入正确的11位手机号")
        String newPhoneNumber,

        @NotBlank(message = "当前密码不能为空")
        String currentPassword,

        @NotBlank(message = "短信验证码ID不能为空")
        String verifyCodeId,

        @NotBlank(message = "短信验证码不能为空")
        @Pattern(regexp = "^\\d{6}$", message = "请输入6位手机验证码")
        String verifyCode
) { }
