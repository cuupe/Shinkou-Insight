package com.cuupe.backend.config.security;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * Authentication limits are deliberately configuration driven so production
 * deployments can tune them without changing code. Redis is used as the
 * shared counter store, which keeps the limits effective across instances.
 */
@Data
@ConfigurationProperties(prefix = "shinkou.security.auth")
public class AuthSecurityProperties {
    private int loginRequestsPerIp = 30;
    private Duration loginRequestWindow = Duration.ofMinutes(5);
    private int loginFailuresPerAccountIp = 5;
    private Duration loginFailureWindow = Duration.ofMinutes(15);

    private int smsRequestsPerIp = 20;
    private int smsRequestsPerPhone = 3;
    private Duration smsRequestWindow = Duration.ofMinutes(10);
    private Duration smsCooldown = Duration.ofSeconds(60);

    private int captchaRequestsPerIp = 30;
    private Duration captchaRequestWindow = Duration.ofMinutes(1);

    private int passwordMutationsPerUser = 5;
    private Duration passwordMutationWindow = Duration.ofMinutes(15);

    private int maxActiveSessionsPerUser = 5;
}
