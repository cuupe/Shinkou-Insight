package com.cuupe.backend.modules.auth.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.config.security.AuthSecurityProperties;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.List;

/** Shared, atomic Redis-backed throttling for authentication endpoints. */
@Service
@RequiredArgsConstructor
public class AuthRateLimiter {
    private static final RedisScript<Long> INCREMENT_WITH_EXPIRY = new DefaultRedisScript<>(
            "local current = redis.call('INCR', KEYS[1]) " +
                    "if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end " +
                    "return current",
            Long.class
    );

    private final StringRedisTemplate redisTemplate;
    private final AuthSecurityProperties properties;

    public void checkLogin(HttpServletRequest request, String phoneNumber) {
        check("login:ip:" + clientAddress(request), properties.getLoginRequestsPerIp(),
                properties.getLoginRequestWindow(), "登录请求过于频繁，请稍后再试");
        check("login:account-ip:" + phoneNumber + ":" + clientAddress(request),
                properties.getLoginFailuresPerAccountIp(), properties.getLoginFailureWindow(),
                "登录请求过于频繁，请稍后再试", false);
    }

    public void recordLoginFailure(HttpServletRequest request, String phoneNumber) {
        increment("auth:login-failure:" + phoneNumber + ":" + clientAddress(request),
                properties.getLoginFailureWindow());
    }

    public void clearLoginFailures(HttpServletRequest request, String phoneNumber) {
        redisTemplate.delete(key("auth:login-failure:" + phoneNumber + ":" + clientAddress(request)));
    }

    public void checkSms(HttpServletRequest request, String phoneNumber) {
        check("sms:ip:" + clientAddress(request), properties.getSmsRequestsPerIp(),
                properties.getSmsRequestWindow(), "验证码请求过于频繁，请稍后再试");
        check("sms:phone:" + phoneNumber, properties.getSmsRequestsPerPhone(),
                properties.getSmsRequestWindow(), "该手机号的验证码请求过于频繁，请稍后再试");
        check("sms:cooldown:" + phoneNumber, 1, properties.getSmsCooldown(),
                "验证码发送过于频繁，请稍后再试");
    }

    public void checkCaptcha(HttpServletRequest request) {
        check("captcha:ip:" + clientAddress(request), properties.getCaptchaRequestsPerIp(),
                properties.getCaptchaRequestWindow(), "验证码请求过于频繁，请稍后再试");
    }

    public void checkPasswordMutation(HttpServletRequest request, Long userId) {
        check("password:user:" + userId + ":" + clientAddress(request),
                properties.getPasswordMutationsPerUser(), properties.getPasswordMutationWindow(),
                "密码操作过于频繁，请稍后再试");
    }

    public void checkVerificationAttempt(HttpServletRequest request, String purpose, String identity) {
        check("verification:ip:" + purpose + ":" + clientAddress(request), 20,
                properties.getLoginRequestWindow(), "验证码校验过于频繁，请稍后再试");
        check("verification:identity:" + purpose + ":" + identity + ":" + clientAddress(request),
                properties.getLoginFailuresPerAccountIp(), properties.getLoginFailureWindow(),
                "验证码校验过于频繁，请稍后再试");
    }

    public String clientAddress(HttpServletRequest request) {
        // Do not trust X-Forwarded-For from the public request. Configure the
        // reverse proxy to pass the real remote address instead.
        String remoteAddress = request == null ? null : request.getRemoteAddr();
        return remoteAddress == null || remoteAddress.isBlank() ? "unknown" : remoteAddress;
    }

    private void check(String suffix, int limit, Duration window, String message) {
        check(suffix, limit, window, message, true);
    }

    private void check(String suffix, int limit, Duration window, String message, boolean countRequest) {
        if (!countRequest) {
            String failureKey = key("auth:login-failure:" + suffix.substring("login:account-ip:".length()));
            String current = redisTemplate.opsForValue().get(failureKey);
            if (current == null || parse(current) < limit) return;
            throw ApiException.tooManyRequests("AUTH_LOGIN_THROTTLED", message);
        }
        Long current = increment(suffix, window);
        if (current != null && current > limit) {
            throw ApiException.tooManyRequests("AUTH_RATE_LIMITED", message);
        }
    }

    private Long increment(String suffix, Duration window) {
        return redisTemplate.execute(
                INCREMENT_WITH_EXPIRY,
                List.of(key(suffix)),
                String.valueOf(Math.max(1, window.toSeconds()))
        );
    }

    private String key(String suffix) {
        return "auth:rate:" + digest(suffix);
    }

    private int parse(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ignored) {
            return Integer.MAX_VALUE;
        }
    }

    private String digest(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (Exception exception) {
            throw new IllegalStateException("无法生成认证限流键", exception);
        }
    }
}
