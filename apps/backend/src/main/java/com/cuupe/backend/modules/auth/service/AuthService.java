package com.cuupe.backend.modules.auth.service;

import com.cuupe.backend.modules.auth.dto.request.LoginRequestByPassword;
import com.cuupe.backend.modules.auth.dto.request.LoginRequestBySms;
import com.cuupe.backend.modules.auth.dto.response.LoginResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.stereotype.Service;

@Service
public interface AuthService {

    LoginResponse loginByPassword(
            @Valid LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) throws Exception;

    LoginResponse loginBySms(
            @Valid LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse);
}
