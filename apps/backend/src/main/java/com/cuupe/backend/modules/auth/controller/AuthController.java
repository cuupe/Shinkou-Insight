package com.cuupe.backend.modules.auth.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.request.RegisterRequest;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.dto.response.RegisterResponse;
import com.cuupe.backend.modules.auth.dto.response.SmsResponse;
import com.cuupe.backend.modules.auth.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

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
    public Result<SmsResponse> getSms(){
        return Result.success("SUCCESS", "短信验证码已发送", authService.generateSms());
    }

    @PostMapping("/register")
    public Result<RegisterResponse> register(
            @Valid @RequestBody RegisterRequest request) {
        RegisterResponse response = authService.register(request);

        return Result.success(response);
    }
}
