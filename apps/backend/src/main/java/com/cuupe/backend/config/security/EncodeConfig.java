package com.cuupe.backend.config.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.DelegatingPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Map;

@Configuration
public class EncodeConfig {
    @Bean
    public PasswordEncoder passwordEncoder() {
        // Keep the {bcrypt} storage format used by existing accounts while
        // raising the work factor for new and transparently-upgraded hashes.
        BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder(12);
        DelegatingPasswordEncoder encoder = new DelegatingPasswordEncoder(
                "bcrypt",
                Map.of("bcrypt", bcrypt)
        );
        encoder.setDefaultPasswordEncoderForMatches(bcrypt);
        return encoder;
    }
}
