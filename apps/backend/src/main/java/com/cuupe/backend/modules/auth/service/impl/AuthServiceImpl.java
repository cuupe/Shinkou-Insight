package com.cuupe.backend.modules.auth.service.impl;

import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.mapper.AuthMapper;
import com.cuupe.backend.modules.auth.service.AuthService;
import com.cuupe.backend.modules.auth.service.CaptchaService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {
    private final CaptchaService captchaService;
    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository securityContextRepository;
    private final AuthMapper authMapper;

    @Override
    public LoginResponse loginByPassword(
            LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) throws Exception {
        if(!captchaService.verifyCaptcha(request.captchaId(), request.captcha())){
            throw new Exception("验证码错误");
        }

        // 把手机号 + 密码包装成“待认证对象”
        Authentication authenticationRequest =
                UsernamePasswordAuthenticationToken.unauthenticated(
                        request.phoneNumber(),
                        request.password()
                );

        // 交给 Spring Security 验证
        Authentication authentication =
                authenticationManager.authenticate(
                        authenticationRequest
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
    public LoginResponse loginBySms(LoginRequestBySms request, HttpServletRequest httpRequest, HttpServletResponse httpResponse) {
        return null;
    }

    private LoginResponse buildLoginResponse(Authentication authentication){
        return new LoginResponse();
    }
}
