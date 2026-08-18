package com.cuupe.backend.modules.auth.service.impl;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.request.RegisterRequest;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.dto.response.RegisterResponse;
import com.cuupe.backend.modules.auth.dto.response.SmsResponse;
import com.cuupe.backend.modules.auth.enums.UserStatus;
import com.cuupe.backend.modules.auth.service.AuthService;
import com.cuupe.backend.modules.auth.service.CaptchaService;
import com.cuupe.backend.modules.user.mapper.UserMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import com.cuupe.backend.utils.RandomUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
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

    private final StringRedisTemplate redisTemplate;
    SecureRandom secureRandom = new SecureRandom();

    private static final int SMS_LENGTH = 6;
    private static final String SMS_PREFIX = "auth:sms:";
    private static final long SMS_EXPIRE_TIME = 300L;


    @Override
    public LoginResponse loginByPassword(
            LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
        }

        UserLoginByPassword user = userMapper.findAuthUserByPhoneNumber(
                request.phoneNumber().trim()
        );
        if (user == null || !user.isEnabled()
                || !passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new BadCredentialsException("手机号或密码错误");
        }

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
    public LoginResponse loginBySms(
            LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
        }

        if (!verifySms(request.verifyCodeId(), request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        UserDetails userDetails = userMapper.findAuthUserByPhoneNumber(
                request.phoneNumber().trim()
        );
        if (userDetails == null || !userDetails.isEnabled()) {
            throw ApiException.unauthorized(
                    "AUTH_ACCOUNT_UNAVAILABLE",
                    "该手机号未注册或账号不可用"
            );
        }
        redisTemplate.delete(request.verifyCodeId());

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
    public SmsResponse generateSms() {
        String smsId = SMS_PREFIX + generateSmsId();
        String sms = RandomUtil.RandomIntSequenceSingle(SMS_LENGTH);
        redisTemplate.opsForValue().set(smsId, sms, Expiration.seconds(SMS_EXPIRE_TIME));

        log.info("验证码 = {}", sms);

        return new SmsResponse(smsId);
    }

    @Override
    public RegisterResponse register(RegisterRequest request) {
        if (!captchaService.verifyCaptcha(request.captchaId(), request.captcha())) {
            throw ApiException.badRequest("CAPTCHA_INVALID", "图片验证码错误或已过期");
        }

        if (!verifySms(request.verifyCodeId(), request.verifyCode())) {
            throw ApiException.badRequest("SMS_CODE_INVALID", "短信验证码错误或已过期");
        }

        String phoneNumber = request.phoneNumber().trim();
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

        return new RegisterResponse("注册成功");
    }

    private String generateSmsId(){
        byte[] bytes = new byte[24];
        secureRandom.nextBytes(bytes);

        return "sms_" + Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(bytes);
    }

    private boolean verifySms(String smsId, String sms){
        if (smsId == null || !smsId.startsWith(SMS_PREFIX)
                || sms == null || !sms.matches("^\\d{6}$")) {
            return false;
        }

        String smsGet = redisTemplate.opsForValue().get(smsId);

        return smsGet != null && smsGet.equals(sms.trim());
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
