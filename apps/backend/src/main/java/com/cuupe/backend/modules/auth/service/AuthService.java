package com.cuupe.backend.modules.auth.service;

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
import com.cuupe.backend.modules.auth.enums.SmsPurpose;
import com.cuupe.backend.modules.user.entity.User;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.stereotype.Service;

@Service
public interface AuthService {

    LoginResponse loginByPassword(
            @Valid LoginRequestByPassword request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse);

    LoginResponse loginBySms(
            @Valid LoginRequestBySms request,
            HttpServletRequest httpRequest,
            HttpServletResponse httpResponse);

    SmsResponse generateSms(String phoneNumber, SmsPurpose purpose);

    RegisterResponse register(@Valid RegisterRequest request);

        User currentUser(Long userId);

        User updateProfile(Long userId, UpdateProfileRequest request);

        User updatePreferences(Long userId, UpdatePreferencesRequest request);

        void updatePassword(Long userId, UpdatePasswordRequest request);

        User updatePhoneNumber(Long userId, UpdatePhoneRequest request);
}
