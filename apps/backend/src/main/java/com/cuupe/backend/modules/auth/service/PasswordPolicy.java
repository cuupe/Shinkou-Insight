package com.cuupe.backend.modules.auth.service;

import com.cuupe.backend.common.exception.ApiException;
import org.springframework.stereotype.Component;

/** Password policy applied to registration, reset and password changes. */
@Component
public class PasswordPolicy {
    public static final int MIN_LENGTH = 12;
    public static final int MAX_LENGTH = 72;

    public void validate(String password, String phoneNumber) {
        if (password == null || password.length() < MIN_LENGTH || password.length() > MAX_LENGTH) {
            throw ApiException.badRequest("PASSWORD_TOO_WEAK", "密码长度必须为 12 至 72 个字符");
        }

        int classes = 0;
        if (password.chars().anyMatch(Character::isUpperCase)) classes++;
        if (password.chars().anyMatch(Character::isLowerCase)) classes++;
        if (password.chars().anyMatch(Character::isDigit)) classes++;
        if (password.chars().anyMatch(character -> !Character.isLetterOrDigit(character))) classes++;
        if (classes < 3) {
            throw ApiException.badRequest("PASSWORD_TOO_WEAK", "密码至少需要包含大写字母、小写字母、数字、特殊字符中的三类");
        }

        if (phoneNumber != null && !phoneNumber.isBlank()
                && password.contains(phoneNumber)) {
            throw ApiException.badRequest("PASSWORD_TOO_WEAK", "密码不能直接使用手机号");
        }

        boolean repeated = password.chars().distinct().count() == 1;
        if (repeated) {
            throw ApiException.badRequest("PASSWORD_TOO_WEAK", "密码不能是重复字符");
        }
    }
}
