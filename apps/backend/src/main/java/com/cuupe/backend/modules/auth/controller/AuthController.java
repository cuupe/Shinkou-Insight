package com.cuupe.backend.modules.auth.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.request.RegisterRequest;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import com.cuupe.backend.modules.auth.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {
    private final AuthService authService;

    @PostMapping("/login/password")
    public Result<LoginResponse> loginByPassword(
            @Valid @RequestBody LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) throws Exception {
        LoginResponse response =
                authService.loginByPassword(request, httpRequest, httpResponse);

        if(response == null){
            return Result.fail("401", "登录验证失败，请联系管理员检查原因。");
        }

        return Result.success(response);
    }

    @PostMapping("/login/sms")
    public Result<LoginResponse> loginBySms(
            @Valid @RequestBody LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse){
        LoginResponse response =
                authService.loginBySms(request, httpRequest, httpResponse);

        return Result.success(response);
    }

    @PostMapping("/register")
    public Result<RegisterRequest> register(
            @Valid @RequestBody RegisterRequest request){
        return null;
    }

}
