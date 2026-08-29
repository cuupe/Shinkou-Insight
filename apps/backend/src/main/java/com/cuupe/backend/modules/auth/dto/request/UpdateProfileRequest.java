package com.cuupe.backend.modules.auth.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdateProfileRequest(
        @NotBlank(message = "用户名不能为空") @Size(min = 2, max = 20, message = "用户名长度必须为 2 至 20 个字符") String userName,
        @Email(message = "邮箱格式不正确") @Size(max = 255, message = "邮箱不能超过 255 个字符") String email,
        @NotBlank(message = "时区不能为空") String timezone
) {}