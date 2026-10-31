package com.cuupe.backend.modules.auth.service;

import com.cuupe.backend.modules.auth.dto.response.CaptchaResponse;
import org.springframework.stereotype.Service;


@Service
public interface CaptchaService {
    public CaptchaResponse generate();

    public boolean verifyCaptcha(String captchaId, String captcha);
}
