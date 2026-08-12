package com.cuupe.backend.modules.auth.service;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.auth.dto.response.CaptchaResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;

@Service
public interface CaptchaService {
    public CaptchaResponse generate();

    public boolean verifyCaptcha(String captchaId, String captcha);
}
