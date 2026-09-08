package com.cuupe.backend.config.security;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import tools.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import jakarta.annotation.PostConstruct;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.AuthenticationProvider;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.security.core.session.SessionRegistryImpl;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.http.MediaType;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
@RequiredArgsConstructor
public class SecurityConfig {
    private final ObjectMapper objectMapper;
    private final AuditLogService auditLogService;
    private final SessionRegistry sessionRegistry;
    private final AuthSecurityProperties authSecurityProperties;

    @Value("${shinkou.security.allowed-origins:http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:4173,http://127.0.0.1:4173,http://localhost:4174,http://127.0.0.1:4174,http://localhost:4175,http://127.0.0.1:4175}")
    private String allowedOrigins;

    @Value("${shinkou.security.environment:development}")
    private String environment;

    @Value("${server.servlet.session.cookie.secure:false}")
    private boolean secureCookies;

    @Value("${shinkou.ai.internal-api-key:}")
    private String internalApiKey;

    @Value("${spring.datasource.password:}")
    private String databasePassword;

    @Value("${spring.data.redis.password:}")
    private String redisPassword;

    @Value("${shinkou.storage.minio.secret-key:}")
    private String minioSecretKey;

    @Value("${shinkou.graph.neo4j.password:}")
    private String graphPassword;

    @PostConstruct
    void validateProductionConfiguration() {
        if (!"production".equalsIgnoreCase(environment)) return;
        if (!secureCookies) {
            throw new IllegalStateException("生产环境必须启用 Secure 会话 Cookie");
        }
        if (internalApiKey == null || internalApiKey.isBlank() || "local-dev-key".equals(internalApiKey)) {
            throw new IllegalStateException("生产环境必须配置非默认的 AI 内部 API 密钥");
        }
        if (isDevelopmentSecret(databasePassword, "shinkou_dev_password")
                || isDevelopmentSecret(redisPassword, "shinkou_redis_password")
                || isDevelopmentSecret(minioSecretKey, "shinkou_minio_password")
                || isDevelopmentSecret(graphPassword, "shinkou_graph_password")) {
            throw new IllegalStateException("生产环境不能使用默认基础设施密码");
        }
        if (allowedOrigins.contains("localhost") || allowedOrigins.contains("127.0.0.1")
                || allowedOrigins.contains("*")) {
            throw new IllegalStateException("生产环境不能允许本地开发 Origin 或通配 Origin");
        }
    }

    private boolean isDevelopmentSecret(String value, String developmentValue) {
        return value == null || value.isBlank() || developmentValue.equals(value);
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(Arrays.stream(allowedOrigins.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isBlank())
                .toList());
        configuration.setAllowCredentials(true);
        configuration.setAllowedMethods(List.of(
                "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of(
                "Accept", "Content-Type", "Last-Event-ID", "X-Requested-With", "X-XSRF-TOKEN"));
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source =
                new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http
    ) throws Exception {
        CookieCsrfTokenRepository csrfTokenRepository =
                CookieCsrfTokenRepository.withHttpOnlyFalse();
        csrfTokenRepository.setCookieCustomizer(cookie -> cookie
                .path("/")
                .httpOnly(false)
                .sameSite("Lax")
                .secure(secureCookies));

        http
                .cors(Customizer.withDefaults())
                // SPA 前端通过 XSRF-TOKEN Cookie + X-XSRF-TOKEN 请求头提交 CSRF token。
                .csrf(csrf -> csrf
                        .csrfTokenRepository(csrfTokenRepository)
                        .ignoringRequestMatchers("/internal/ai/**")
                        .spa())
                .securityContext(
                        sc -> sc.securityContextRepository(securityContextRepository()))
                .sessionManagement(session ->
                        session.sessionCreationPolicy(
                                SessionCreationPolicy.IF_REQUIRED
                        ).sessionFixation(sessionFixation ->
                                sessionFixation.migrateSession()
                        ).maximumSessions(authSecurityProperties.getMaxActiveSessionsPerUser())
                        .maxSessionsPreventsLogin(false)
                        .sessionRegistry(sessionRegistry)
                )
                .headers(headers -> headers
                        .frameOptions(frame -> frame.deny())
                        .contentTypeOptions(Customizer.withDefaults())
                        .cacheControl(Customizer.withDefaults())
                        .referrerPolicy(referrer -> referrer.policy(
                                ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers(
                                "/auth/captcha",
                                "/auth/csrf",
                                "/auth/login/*",
                                "/auth/register",
                                "/auth/sms",
                                "/auth/password/reset"
                        ).permitAll()
                        .requestMatchers("/internal/ai/**").permitAll()
                        .anyRequest()
                        .authenticated()
                )
                .formLogin(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint(
                                (request, response, authException) -> {
                                    writeError(
                                            response,
                                            HttpServletResponse.SC_UNAUTHORIZED,
                                            "AUTHENTICATION_REQUIRED",
                                            "请先登录后再进行此操作"
                                    );
                                }
                        )
                        .accessDeniedHandler(
                                (request, response, accessDeniedException) -> {
                                    writeError(
                                            response,
                                            HttpServletResponse.SC_FORBIDDEN,
                                            "ACCESS_DENIED",
                                            "当前账号没有执行此操作的权限"
                                    );
                                }
                        )
                )
                .logout(logout -> logout
                        .logoutUrl("/auth/logout")
                        .invalidateHttpSession(true)
                        .clearAuthentication(true)
                        .deleteCookies("JSESSIONID", "XSRF-TOKEN")
                        .logoutSuccessHandler((request, response, authentication) -> {
                            if (authentication != null && authentication.getPrincipal() instanceof UserLoginByPassword user) {
                                if (request.getSession(false) != null) {
                                    sessionRegistry.removeSessionInformation(request.getSession(false).getId());
                                }
                                auditLogService.record(null, null, user.getId(), "LOGOUT_SUCCEEDED", "AUTH", user.getId());
                            }
                            writeSuccess(response, "登出成功");
                        })
                );

        return http.build();
    }

    private void writeError(
            HttpServletResponse response,
            int status,
            String code,
            String message
    ) throws IOException {
        response.setStatus(status);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(
                response.getWriter(),
                Result.fail(code, message)
        );
    }

    private void writeSuccess(
            HttpServletResponse response,
            String message
    ) throws IOException {
        response.setStatus(HttpServletResponse.SC_OK);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(
                response.getWriter(),
                Result.success("SUCCESS", message, null)
        );
    }

    @Bean
    public AuthenticationManager authenticationManager(
            AuthenticationConfiguration authenticationConfiguration
    ) throws Exception {
        return authenticationConfiguration.getAuthenticationManager();
    }

    @Bean
    public AuthenticationProvider authenticationProvider(
            UserDetailsService userDetailsService,
            PasswordEncoder passwordEncoder
    ) {
        DaoAuthenticationProvider provider =
                new DaoAuthenticationProvider(userDetailsService);
        provider.setPasswordEncoder(passwordEncoder);
        return provider;
    }

    @Bean
    public SecurityContextRepository securityContextRepository() {
        return new HttpSessionSecurityContextRepository();
    }

    @Bean
    public SessionRegistry sessionRegistry() {
        return new SessionRegistryImpl();
    }
}
