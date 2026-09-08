package com.cuupe.backend.modules.auth.service.impl;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.request.RegisterRequest;
import com.cuupe.backend.modules.auth.dto.request.ResetPasswordRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePasswordRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePhoneRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePreferencesRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdateProfileRequest;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.dto.response.RegisterResponse;
import com.cuupe.backend.modules.auth.dto.response.SmsResponse;
import com.cuupe.backend.modules.auth.enums.SmsPurpose;
import com.cuupe.backend.modules.auth.enums.UserStatus;
import com.cuupe.backend.modules.auth.service.AuthRateLimiter;
import com.cuupe.backend.modules.auth.service.AuthService;
import com.cuupe.backend.modules.auth.service.CaptchaService;
import com.cuupe.backend.modules.auth.service.PasswordPolicy;
import com.cuupe.backend.modules.auth.service.SessionSecurityService;
import com.cuupe.backend.modules.user.entity.User;
import com.cuupe.backend.modules.user.mapper.UserMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.entity.Workspace;
import com.cuupe.backend.modules.workspace.service.WorkspaceService;
import jakarta.annotation.PostConstruct;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.Collections;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {
    private static final int SMS_LENGTH = 6;
    private static final String SMS_PREFIX = "auth:sms:";
    private static final long SMS_EXPIRE_TIME = 300L;

    private static final RedisScript<Long> VERIFY_AND_DELETE_SMS_SCRIPT = new DefaultRedisScript<>(
            "local value = redis.call('GET', KEYS[1]) " +
                    "if value == ARGV[1] then " +
                    "redis.call('DEL', KEYS[1]) " +
                    "return 1 " +
                    "end " +
                    "return 0",
            Long.class
    );

    private final CaptchaService captchaService;
    private final SecurityContextRepository securityContextRepository;
    private final PasswordEncoder passwordEncoder;
    private final UserMapper userMapper;
    private final WorkspaceService workspaceService;
    private final AuditLogService auditLogService;
    private final StringRedisTemplate redisTemplate;
    private final AuthRateLimiter rateLimiter;
    private final PasswordPolicy passwordPolicy;
    private final SessionSecurityService sessionSecurityService;

    private final SecureRandom secureRandom = new SecureRandom();
    private String dummyPasswordHash;

    @PostConstruct
    void initializeTimingDefense() {
        // A missing account still performs a BCrypt comparison, reducing
        // username/account enumeration through response timing.
        dummyPasswordHash = passwordEncoder.encode("not-a-real-password-" + secureRandom.nextLong());
    }

    @Override
    public LoginResponse loginByPassword(
            LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        String phoneNumber = request.phoneNumber().trim();
        rateLimiter.checkLogin(httpRequest, phoneNumber);

        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            rateLimiter.recordLoginFailure(httpRequest, phoneNumber);
            recordLoginFailure(httpRequest, phoneNumber, "PASSWORD", "CAPTCHA_INVALID");
            throw new BadCredentialsException("invalid credentials");
        }

        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        String hashForTimingCheck = user != null && user.isEnabled() && user.getPassword() != null
                ? user.getPassword() : dummyPasswordHash;
        boolean passwordMatches = passwordEncoder.matches(request.password(), hashForTimingCheck);
        boolean credentialsValid = user != null && user.isEnabled()
                && user.getPassword() != null && passwordMatches;

        if (!credentialsValid) {
            rateLimiter.recordLoginFailure(httpRequest, phoneNumber);
            recordLoginFailure(httpRequest, phoneNumber, "PASSWORD", "INVALID_CREDENTIALS");
            throw new BadCredentialsException("invalid credentials");
        }

        rateLimiter.clearLoginFailures(httpRequest, phoneNumber);
        if (passwordEncoder.upgradeEncoding(user.getPassword())) {
            userMapper.updatePassword(user.getId(), passwordEncoder.encode(request.password()));
        }
        userMapper.updateLoginAt(user.getId());

        Authentication authentication = authenticateAndPersist(user, httpRequest, httpResponse);
        auditLogService.record(null, null, user.getId(), "LOGIN_SUCCEEDED",
                "AUTH", user.getId(), Map.of("method", "PASSWORD"));
        return buildLoginResponse(authentication);
    }

    @Override
    public LoginResponse loginBySms(
            LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        String phoneNumber = request.phoneNumber().trim();
        rateLimiter.checkLogin(httpRequest, phoneNumber);

        if (!verifySms(request.verifyCodeId(), phoneNumber, SmsPurpose.LOGIN, request.verifyCode())) {
            rateLimiter.recordLoginFailure(httpRequest, phoneNumber);
            recordLoginFailure(httpRequest, phoneNumber, "SMS", "SMS_INVALID");
            throw new BadCredentialsException("invalid credentials");
        }

        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        if (user == null || !user.isEnabled()) {
            rateLimiter.recordLoginFailure(httpRequest, phoneNumber);
            recordLoginFailure(httpRequest, phoneNumber, "SMS", "INVALID_ACCOUNT");
            throw new BadCredentialsException("invalid credentials");
        }

        rateLimiter.clearLoginFailures(httpRequest, phoneNumber);
        userMapper.updateLoginAt(user.getId());
        Authentication authentication = authenticateAndPersist(user, httpRequest, httpResponse);
        auditLogService.record(null, null, user.getId(), "LOGIN_SUCCEEDED",
                "AUTH", user.getId(), Map.of("method", "SMS"));
        return buildLoginResponse(authentication);
    }

    @Override
    public SmsResponse generateSms(
            String phoneNumber,
            SmsPurpose purpose,
            String captchaId,
            String captcha,
            HttpServletRequest httpRequest) {
        if (phoneNumber == null || !phoneNumber.matches("^1\\d{10}$")) {
            throw ApiException.badRequest("INVALID_PHONE", "手机号格式不正确");
        }

        rateLimiter.checkSms(httpRequest, phoneNumber);
        if (purpose == SmsPurpose.REGISTER
                || purpose == SmsPurpose.LOGIN
                || purpose == SmsPurpose.PASSWORD_RESET) {
            if (!captchaService.verifyCaptcha(captchaId, captcha)) {
                throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
            }
        }

        if ((purpose == SmsPurpose.REGISTER || purpose == SmsPurpose.PHONE_CHANGE)
                && userMapper.existPhoneNumber(phoneNumber)) {
            throw ApiException.conflict("PHONE_ALREADY_REGISTERED", "该手机号已注册");
        }

        String smsId = SMS_PREFIX + generateSmsId();
        String sms = String.format("%0" + SMS_LENGTH + "d", secureRandom.nextInt(1_000_000));
        String value = phoneNumber + "|" + purpose.name() + "|" + sms;
        redisTemplate.opsForValue().set(smsId, value, Duration.ofSeconds(SMS_EXPIRE_TIME));

        // Never log the code. A real SMS provider should be integrated here.
        return new SmsResponse(smsId);
    }

    @Override
    public RegisterResponse register(RegisterRequest request, HttpServletRequest httpRequest) {
        String phoneNumber = request.phoneNumber().trim();
        passwordPolicy.validate(request.password(), phoneNumber);

        rateLimiter.checkVerificationAttempt(httpRequest, "REGISTER", phoneNumber);
        if (!verifySms(request.verifyCodeId(), phoneNumber, SmsPurpose.REGISTER, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        if (userMapper.existPhoneNumber(phoneNumber)) {
            throw ApiException.conflict("PHONE_ALREADY_REGISTERED", "该手机号已注册");
        }

        userMapper.createNewUser(
                request.userName().trim(),
                phoneNumber,
                passwordEncoder.encode(request.password()),
                LocalDateTime.now(),
                UserStatus.NORMAL_STATUS()
        );

        UserLoginByPassword createdUser = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        if (createdUser != null) {
            Workspace createdWorkspace = workspaceService.create(
                    request.userName().trim() + " 的工作区",
                    null,
                    null,
                    createdUser.getId()
            );
            auditLogService.record(createdWorkspace.getId(), null, createdUser.getId(),
                    "WORKSPACE_CREATED", "WORKSPACE", createdWorkspace.getId(),
                    Map.of("reason", "REGISTRATION"));
            auditLogService.record(createdWorkspace.getId(), null, createdUser.getId(),
                    "USER_REGISTERED", "USER", createdUser.getId());
        }

        return new RegisterResponse("注册成功");
    }

    @Override
    public void resetPassword(ResetPasswordRequest request, HttpServletRequest httpRequest) {
        String phoneNumber = request.phoneNumber().trim();
        passwordPolicy.validate(request.newPassword(), phoneNumber);

        rateLimiter.checkVerificationAttempt(httpRequest, "PASSWORD_RESET", phoneNumber);
        if (!verifySms(request.verifyCodeId(), phoneNumber, SmsPurpose.PASSWORD_RESET, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        if (user == null || !user.isEnabled()) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        userMapper.updatePassword(user.getId(), passwordEncoder.encode(request.newPassword()));
        sessionSecurityService.expireAllSessions(user.getUsername());
        auditLogService.record(null, null, user.getId(), "PASSWORD_RESET",
                "USER", user.getId());
    }

    @Override
    public User currentUser(Long userId) {
        User user = userMapper.findUserById(userId);
        if (user == null || user.getStatus() == null || user.getStatus() != UserStatus.NORMAL_STATUS()) {
            throw ApiException.unauthorized("AUTH_ACCOUNT_UNAVAILABLE", "当前账号不可用");
        }
        user.setPassword(null);
        return user;
    }

    @Override
    public User updateProfile(Long userId, UpdateProfileRequest request) {
        currentUser(userId);
        userMapper.updateProfile(userId, request.userName().trim(), blankToNull(request.email()),
                request.timezone().trim());
        auditLogService.record(null, null, userId, "PROFILE_UPDATED", "USER", userId);
        return currentUser(userId);
    }

    @Override
    public User updatePreferences(Long userId, UpdatePreferencesRequest request) {
        currentUser(userId);
        String preferences = "{\"activity\":" + request.activity()
                + ",\"weeklyDigest\":" + request.weeklyDigest() + "}";
        userMapper.updateNotificationPreferences(userId, preferences);
        auditLogService.record(null, null, userId, "USER_PREFERENCES_UPDATED", "USER", userId);
        return currentUser(userId);
    }

    @Override
    public void updatePassword(Long userId, UpdatePasswordRequest request, HttpServletRequest httpRequest) {
        rateLimiter.checkPasswordMutation(httpRequest, userId);
        User current = currentUser(userId);
        passwordPolicy.validate(request.newPassword(), current.getPhoneNumber());

        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(current.getPhoneNumber());
        if (user == null || !passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw ApiException.badRequest("CURRENT_PASSWORD_INVALID", "当前密码不正确");
        }
        if (!verifySms(request.verifyCodeId(), current.getPhoneNumber(),
                SmsPurpose.PASSWORD_CHANGE, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }
        if (passwordEncoder.matches(request.newPassword(), user.getPassword())) {
            throw ApiException.badRequest("PASSWORD_UNCHANGED", "新密码不能与当前密码相同");
        }

        userMapper.updatePassword(userId, passwordEncoder.encode(request.newPassword()));
        String currentSessionId = httpRequest.getSession(false) == null
                ? null : httpRequest.getSession(false).getId();
        sessionSecurityService.expireOtherSessions(user.getUsername(), currentSessionId);
        auditLogService.record(null, null, userId, "PASSWORD_UPDATED", "USER", userId);
    }

    @Override
    public User updatePhoneNumber(Long userId, UpdatePhoneRequest request, HttpServletRequest httpRequest) {
        User current = currentUser(userId);
        String newPhoneNumber = request.newPhoneNumber().trim();
        if (newPhoneNumber.equals(current.getPhoneNumber())) {
            throw ApiException.badRequest("PHONE_UNCHANGED", "新手机号不能与当前手机号相同");
        }

        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(current.getPhoneNumber());
        if (user == null || !passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw ApiException.badRequest("CURRENT_PASSWORD_INVALID", "当前密码不正确");
        }
        if (userMapper.existPhoneNumber(newPhoneNumber)) {
            throw ApiException.conflict("PHONE_ALREADY_REGISTERED", "该手机号已注册");
        }
        rateLimiter.checkVerificationAttempt(httpRequest, "PHONE_CHANGE", newPhoneNumber);
        if (!verifySms(request.verifyCodeId(), newPhoneNumber, SmsPurpose.PHONE_CHANGE, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        userMapper.updatePhoneNumber(userId, newPhoneNumber);
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof UserLoginByPassword principal
                && userId.equals(principal.getId())) {
            principal.setPhoneNumber(newPhoneNumber);
        }
        String currentSessionId = httpRequest.getSession(false) == null
                ? null : httpRequest.getSession(false).getId();
        sessionSecurityService.expireOtherSessions(user.getUsername(), currentSessionId);
        auditLogService.record(null, null, userId, "PHONE_UPDATED", "USER", userId);
        return currentUser(userId);
    }

    private Authentication authenticateAndPersist(
            UserLoginByPassword user,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        httpRequest.getSession(true);
        httpRequest.changeSessionId();

        Authentication authentication = UsernamePasswordAuthenticationToken.authenticated(
                user, null, user.getAuthorities());
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, httpRequest, httpResponse);

        HttpSession session = httpRequest.getSession(false);
        if (session != null) {
            sessionSecurityService.register(session.getId(), user.getUsername());
        }
        return authentication;
    }

    private void recordLoginFailure(
            HttpServletRequest request,
            String phoneNumber,
            String method,
            String reason) {
        auditLogService.recordFailure(null, null, null, "LOGIN_FAILED", "AUTH", null,
                Map.of(
                        "method", method,
                        "reason", reason,
                        "phone", maskPhone(phoneNumber),
                        "ip", rateLimiter.clientAddress(request)
                ));
    }

    private String maskPhone(String phoneNumber) {
        if (phoneNumber == null || phoneNumber.length() < 7) return "***";
        return phoneNumber.substring(0, 3) + "****" + phoneNumber.substring(phoneNumber.length() - 4);
    }

    private boolean verifySms(String smsId, String phoneNumber, SmsPurpose purpose, String sms) {
        if (smsId == null || !smsId.startsWith(SMS_PREFIX)
                || sms == null || !sms.matches("^\\d{6}$")) {
            return false;
        }

        String expected = phoneNumber.trim() + "|" + purpose.name() + "|" + sms.trim();
        Long verified = redisTemplate.execute(
                VERIFY_AND_DELETE_SMS_SCRIPT,
                Collections.singletonList(smsId),
                expected
        );
        return Long.valueOf(1L).equals(verified);
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private String generateSmsId() {
        byte[] bytes = new byte[24];
        secureRandom.nextBytes(bytes);
        return "sms_" + Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private LoginResponse buildLoginResponse(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (principal instanceof UserLoginByPassword user) {
            return new LoginResponse(user.getId(), user.getPhoneNumber(), user.getDisplayName());
        }
        return new LoginResponse(null, authentication.getName(), null);
    }

}
