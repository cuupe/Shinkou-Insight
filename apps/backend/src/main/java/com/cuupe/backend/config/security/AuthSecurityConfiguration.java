package com.cuupe.backend.config.security;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(AuthSecurityProperties.class)
public class AuthSecurityConfiguration {
}
