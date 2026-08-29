package com.cuupe.backend.modules.auth.service.impl;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.request.RegisterRequest;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.dto.response.RegisterResponse;
import com.cuupe.backend.modules.auth.dto.response.SmsResponse;
import com.cuupe.backend.modules.auth.dto.request.UpdatePasswordRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePhoneRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePreferencesRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdateProfileRequest;
import com.cuupe.backend.modules.auth.enums.UserStatus;
import com.cuupe.backend.modules.auth.enums.SmsPurpose;
import com.cuupe.backend.modules.auth.service.AuthService;
import com.cuupe.backend.modules.auth.service.CaptchaService;
import com.cuupe.backend.modules.user.mapper.UserMapper;
import com.cuupe.backend.modules.user.entity.User;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.modules.workspace.service.WorkspaceService;
import com.cuupe.backend.utils.RandomUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.types.Expiration;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;


@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {
    private final CaptchaService captchaService;
    private final SecurityContextRepository securityContextRepository;
    private final PasswordEncoder passwordEncoder;
    private final UserMapper userMapper;
    private final WorkspaceService workspaceService;

    private final StringRedisTemplate redisTemplate;
    SecureRandom secureRandom = new SecureRandom();

    private static final int SMS_LENGTH = 6;
    private static final String SMS_PREFIX = "auth:sms:";
    private static final long SMS_EXPIRE_TIME = 300L;
    private static final String LOGIN_FAILURE_PREFIX = "auth:login-fail:";
    private static final int MAX_LOGIN_FAILURES = 5;
    private static final long LOGIN_LOCK_SECONDS = 900L;


    @Override
    public LoginResponse loginByPassword(
            LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
        }

        String phoneNumber = request.phoneNumber().trim();
        checkLoginLock(phoneNumber);
        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        if (user == null || !user.isEnabled()
                || !passwordEncoder.matches(request.password(), user.getPassword())) {
            recordLoginFailure(phoneNumber);
            throw new BadCredentialsException("手机号或密码错误");
        }
        clearLoginFailures(phoneNumber);
        userMapper.updateLoginAt(user.getId());

        Authentication authentication =
                UsernamePasswordAuthenticationToken.authenticated(
                        user,
                        null,
                        user.getAuthorities()
                );

        // 创建登录后的 SecurityContext
        SecurityContext context =
                SecurityContextHolder.createEmptyContext();

        context.setAuthentication(authentication);

        SecurityContextHolder.setContext(context);

        // 保存到 HttpSession
        securityContextRepository.saveContext(
                context,
                httpRequest,
                httpResponse
        );

        // 返回前端用户信息
        return buildLoginResponse(authentication);
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
        userMapper.updateProfile(userId, request.userName().trim(), blankToNull(request.email()), request.timezone().trim());
        return currentUser(userId);
    }

    @Override
    public User updatePreferences(Long userId, UpdatePreferencesRequest request) {
        currentUser(userId);
        String preferences = "{\"activity\":" + request.activity() + ",\"weeklyDigest\":" + request.weeklyDigest() + "}";
        userMapper.updateNotificationPreferences(userId, preferences);
        return currentUser(userId);
    }

    @Override
    public void updatePassword(Long userId, UpdatePasswordRequest request) {
        User current = currentUser(userId);
        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(current.getPhoneNumber());
        if (user == null || !passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw ApiException.badRequest("CURRENT_PASSWORD_INVALID", "当前密码不正确");
        }
        if (!verifySms(request.verifyCodeId(), current.getPhoneNumber(), SmsPurpose.PASSWORD_CHANGE, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }
        if (passwordEncoder.matches(request.newPassword(), user.getPassword())) {
            throw ApiException.badRequest("PASSWORD_UNCHANGED", "新密码不能与当前密码相同");
        }
        redisTemplate.delete(request.verifyCodeId());
        userMapper.updatePassword(userId, passwordEncoder.encode(request.newPassword()));
    }

    @Override
    public User updatePhoneNumber(Long userId, UpdatePhoneRequest request) {
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
        if (!verifySms(request.verifyCodeId(), newPhoneNumber, SmsPurpose.PHONE_CHANGE, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }
        redisTemplate.delete(request.verifyCodeId());
        userMapper.updatePhoneNumber(userId, newPhoneNumber);

        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof UserLoginByPassword principal
                && userId.equals(principal.getId())) {
            principal.setPhoneNumber(newPhoneNumber);
        }
        return currentUser(userId);
    }

    @Override
    public LoginResponse loginBySms(
            LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
        }

        String phoneNumber = request.phoneNumber().trim();
        if (!verifySms(request.verifyCodeId(), phoneNumber, SmsPurpose.LOGIN, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        UserDetails userDetails = userMapper.findAuthUserByPhoneNumber(
                phoneNumber
        );
        if (userDetails == null || !userDetails.isEnabled()) {
            throw ApiException.unauthorized(
                    "AUTH_ACCOUNT_UNAVAILABLE",
                    "该手机号未注册或账号不可用"
            );
        }
        redisTemplate.delete(request.verifyCodeId());
        if (userDetails instanceof UserLoginByPassword user) {
            userMapper.updateLoginAt(user.getId());
        }

        Authentication authentication =
                UsernamePasswordAuthenticationToken.authenticated(
                        userDetails,
                        null,
                        userDetails.getAuthorities()
                );
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, httpRequest, httpResponse);

        return buildLoginResponse(authentication);
    }

    @Override
    public SmsResponse generateSms(String phoneNumber, SmsPurpose purpose) {
        if (!phoneNumber.matches("^1\\d{10}$")) {
            throw ApiException.badRequest("INVALID_PHONE", "手机号格式不正确");
        }
        if ((purpose == SmsPurpose.REGISTER || purpose == SmsPurpose.PHONE_CHANGE)
                && userMapper.existPhoneNumber(phoneNumber)) {
            throw ApiException.conflict("PHONE_ALREADY_REGISTERED", "该手机号已注册");
        }
        String smsId = SMS_PREFIX + generateSmsId();
        String sms = RandomUtil.RandomIntSequenceSingle(SMS_LENGTH);
        String value = phoneNumber + "|" + purpose.name() + "|" + sms;
        redisTemplate.opsForValue().set(smsId, value, Expiration.seconds(SMS_EXPIRE_TIME));

        // 当前尚未接入短信供应商，开发环境通过日志读取验证码。
        log.info("验证码 = {}", sms);

        return new SmsResponse(smsId);
    }

    @Override
    public RegisterResponse register(RegisterRequest request) {
        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
        }

        String phoneNumber = request.phoneNumber().trim();
        if (!verifySms(request.verifyCodeId(), phoneNumber, SmsPurpose.REGISTER, request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        if (userMapper.existPhoneNumber(phoneNumber)) {
            throw ApiException.conflict("PHONE_ALREADY_REGISTERED", "该手机号已注册");
        }
        redisTemplate.delete(request.verifyCodeId());

        userMapper.createNewUser(
                request.userName().trim(),
                phoneNumber,
                passwordEncoder.encode(request.password()),
                LocalDateTime.now(),
                UserStatus.NORMAL_STATUS()
        );

        // 新用户自动获得一个默认工作区，避免登录后无工作区可用
        UserDetails created = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        if (created instanceof UserLoginByPassword createdUser) {
            workspaceService.create(
                    request.userName().trim() + " 的工作区",
                    null,
                    null,
                    createdUser.getId()
            );
        }

        return new RegisterResponse("注册成功");
    }

    private String generateSmsId(){
        byte[] bytes = new byte[24];
        secureRandom.nextBytes(bytes);

        return "sms_" + Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(bytes);
    }

    private boolean verifySms(String smsId, String phoneNumber, SmsPurpose purpose, String sms){
        if (smsId == null || !smsId.startsWith(SMS_PREFIX)
                || sms == null || !sms.matches("^\\d{6}$")) {
            return false;
        }

        String smsGet = redisTemplate.opsForValue().get(smsId);
        String expected = phoneNumber.trim() + "|" + purpose.name() + "|" + sms.trim();

        return smsGet != null && smsGet.equals(expected);
    }

    private String blankToNull(String value) { return value == null || value.isBlank() ? null : value.trim(); }

    private void checkLoginLock(String phoneNumber) {
        String failures = redisTemplate.opsForValue().get(LOGIN_FAILURE_PREFIX + phoneNumber);
        if (failures != null && Integer.parseInt(failures) >= MAX_LOGIN_FAILURES) {
            throw ApiException.unauthorized("AUTH_ACCOUNT_LOCKED", "登录失败次数过多，请 15 分钟后重试");
        }
    }

    private void recordLoginFailure(String phoneNumber) {
        String key = LOGIN_FAILURE_PREFIX + phoneNumber;
        Long failures = redisTemplate.opsForValue().increment(key);
        if (failures != null && failures == 1L) {
            redisTemplate.expire(key, java.time.Duration.ofSeconds(LOGIN_LOCK_SECONDS));
        }
    }

    private void clearLoginFailures(String phoneNumber) {
        redisTemplate.delete(LOGIN_FAILURE_PREFIX + phoneNumber);
    }

    private LoginResponse buildLoginResponse(Authentication authentication){
        Object principal = authentication.getPrincipal();
        if (principal instanceof UserLoginByPassword user) {
            return new LoginResponse(
                    user.getId(),
                    user.getPhoneNumber(),
                    user.getDisplayName()
            );
        }

        return new LoginResponse(null, authentication.getName(), null);
    }

}
