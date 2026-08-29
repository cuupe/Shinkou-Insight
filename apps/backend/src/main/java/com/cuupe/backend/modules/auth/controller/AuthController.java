package com.cuupe.backend.modules.auth.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.request.RegisterRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePasswordRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePhoneRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdatePreferencesRequest;
import com.cuupe.backend.modules.auth.dto.request.UpdateProfileRequest;
import com.cuupe.backend.modules.auth.enums.SmsPurpose;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.dto.response.RegisterResponse;
import com.cuupe.backend.modules.auth.dto.response.SmsResponse;
import com.cuupe.backend.modules.auth.service.AuthService;
import com.cuupe.backend.modules.user.entity.User;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {
    private final AuthService authService;

    @PostMapping("/login/password")
    public Result<LoginResponse> loginByPassword(
            @Valid @RequestBody LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {

        LoginResponse response =
                authService.loginByPassword(request, httpRequest, httpResponse);

        return Result.success("SUCCESS", "登录成功", response);
    }

    @PostMapping("/login/sms")
    public Result<LoginResponse> loginBySms(
            @Valid @RequestBody LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        LoginResponse response =
                authService.loginBySms(request, httpRequest, httpResponse);

        return Result.success("SUCCESS", "登录成功", response);
    }

    @GetMapping("/sms")
    public Result<SmsResponse> getSms(
            @RequestParam String phoneNumber,
            @RequestParam SmsPurpose purpose,
            Authentication authentication) {
        String normalizedPhone = phoneNumber.trim();
        if (purpose == SmsPurpose.PASSWORD_CHANGE || purpose == SmsPurpose.PHONE_CHANGE) {
            if (!isAuthenticated(authentication)) {
                throw ApiException.unauthorized(
                        "AUTHENTICATION_REQUIRED", "请先登录后再获取安全验证码");
            }
            if (purpose == SmsPurpose.PASSWORD_CHANGE) {
                UserLoginByPassword user = (UserLoginByPassword) authentication.getPrincipal();
                if (!normalizedPhone.equals(user.getPhoneNumber())) {
                    throw ApiException.badRequest(
                            "PHONE_VERIFICATION_MISMATCH", "验证码手机号必须是当前账号绑定的手机号");
                }
            }
        }
        return Result.success("SUCCESS", "短信验证码已发送", authService.generateSms(normalizedPhone, purpose));
    }

    @PostMapping("/register")
    public Result<RegisterResponse> register(
            @Valid @RequestBody RegisterRequest request) {
        RegisterResponse response = authService.register(request);

        return Result.success(response);
    }

    @GetMapping("/me")
    public Result<User> me(Authentication authentication) {
        UserLoginByPassword user = (UserLoginByPassword) authentication.getPrincipal();
        return Result.success(authService.currentUser(user.getId()));
    }

    @PatchMapping("/me")
    public Result<User> updateProfile(@Valid @RequestBody UpdateProfileRequest request, Authentication authentication) {
        return Result.success(authService.updateProfile(userId(authentication), request));
    }

    @PatchMapping("/me/preferences")
    public Result<User> updatePreferences(@Valid @RequestBody UpdatePreferencesRequest request, Authentication authentication) {
        return Result.success(authService.updatePreferences(userId(authentication), request));
    }

    @PutMapping("/me/password")
    public Result<Void> updatePassword(@Valid @RequestBody UpdatePasswordRequest request, Authentication authentication) {
        authService.updatePassword(userId(authentication), request);
        return Result.success();
    }

    @PutMapping("/me/phone")
    public Result<User> updatePhone(
            @Valid @RequestBody UpdatePhoneRequest request,
            Authentication authentication) {
        return Result.success(authService.updatePhoneNumber(userId(authentication), request));
    }

    private boolean isAuthenticated(Authentication authentication) {
        return authentication != null
                && authentication.isAuthenticated()
                && !(authentication instanceof AnonymousAuthenticationToken);
    }

    private Long userId(Authentication authentication) {
        return ((UserLoginByPassword) authentication.getPrincipal()).getId();
    }
}
