package com.cuupe.backend.modules.auth.service.impl;

import com.cuupe.backend.modules.auth.dto.response.CaptchaResponse;
import com.cuupe.backend.modules.auth.service.CaptchaService;
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
@RequiredArgsConstructor
public class CaptchaServiceImpl implements CaptchaService {
    private static final int WIDTH = 140;
    private static final int HEIGHT = 50;

    private static final int CODE_LENGTH = 4;

    private static final char[] CHARACTERS =
            "23456789ABCDEFGHJKMNPQRSTUVWXYZ".toCharArray();
    private static final Duration CAPTCHA_TTL =
            Duration.ofMinutes(2);
    private static final String REDIS_PREFIX = "auth:captcha:";
    private final StringRedisTemplate redisTemplate;
    private final SecureRandom secureRandom =
            new SecureRandom();

    public CaptchaResponse generate() {
        String code = generateCode();

        String captchaId = generateCaptchaId();

        redisTemplate.opsForValue().set(
                REDIS_PREFIX + captchaId,
                code,
                CAPTCHA_TTL
        );

        String image = generateImage(code);

        return new CaptchaResponse(
                captchaId,
                image
        );
    }

    @Override
    public boolean verifyCaptcha(String captchaId, String captcha) {
        String captcha_get = redisTemplate.opsForValue().get(
                REDIS_PREFIX + captchaId);

        return captcha_get != null && !captcha_get.equals(captcha);
    }


    private String generateCode(){
        StringBuilder sb = new StringBuilder(CODE_LENGTH);

        for(int i = 0; i < CODE_LENGTH; ++i){
            int index = secureRandom.nextInt(
                    CHARACTERS.length
            );

            sb.append(CHARACTERS[index]);
        }

        return sb.toString();
    }

    private String generateCaptchaId(){
        byte[] bytes = new byte[24];
        secureRandom.nextBytes(bytes);

        return "cp_"+ Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(bytes);
    }

    private String generateImage(String code){
        BufferedImage image = new BufferedImage(
                WIDTH, HEIGHT, BufferedImage.TYPE_INT_RGB
        );

        Graphics2D graphics = image.createGraphics();

        try {
            configureGraphics(graphics);

            drawBackground(graphics);

            drawNoiseLines(graphics);

            drawNoisePoints(graphics);

            drawCharacters(
                    graphics,
                    code
            );

            return toBase64(image);

        } finally {
            graphics.dispose();
        }
    }

    private void configureGraphics(
            Graphics2D graphics
    ){
        graphics.setRenderingHint(
                RenderingHints.KEY_ANTIALIASING,
                RenderingHints.VALUE_ANTIALIAS_ON
        );

        graphics.setRenderingHint(
                RenderingHints.KEY_TEXT_ANTIALIASING,
                RenderingHints.VALUE_TEXT_ANTIALIAS_ON
        );
    }

    private void drawBackground(
            Graphics2D graphics
    ) {
        graphics.setColor(
                new Color(245, 245, 245)
        );

        graphics.fillRect(
                0,
                0,
                WIDTH,
                HEIGHT
        );
    }

    private void drawNoiseLines(
            Graphics2D graphics
    ) {
        for (int i = 0; i < 6; i++) {

            graphics.setColor(
                    randomLightColor()
            );

            int x1 =
                    secureRandom.nextInt(WIDTH);

            int y1 =
                    secureRandom.nextInt(HEIGHT);

            int x2 =
                    secureRandom.nextInt(WIDTH);

            int y2 =
                    secureRandom.nextInt(HEIGHT);

            graphics.drawLine(
                    x1,
                    y1,
                    x2,
                    y2
            );
        }
    }

    private void drawNoisePoints(
            Graphics2D graphics
    ) {
        for (int i = 0; i < 70; i++) {

            graphics.setColor(
                    randomLightColor()
            );

            int x =
                    secureRandom.nextInt(WIDTH);

            int y =
                    secureRandom.nextInt(HEIGHT);

            graphics.fillRect(
                    x,
                    y,
                    2,
                    2
            );
        }
    }

    private void drawCharacters(
            Graphics2D graphics,
            String code
    ) {

        int charWidth =
                WIDTH / (CODE_LENGTH + 1);

        for (int i = 0; i < code.length(); i++) {

            char character =
                    code.charAt(i);

            int fontSize =
                    28 + secureRandom.nextInt(5);

            Font font =
                    new Font(
                            Font.SANS_SERIF,
                            Font.BOLD,
                            fontSize
                    );

            graphics.setFont(font);

            graphics.setColor(
                    randomDarkColor()
            );

            int x =
                    14 + i * charWidth;

            int y =
                    32 +
                            secureRandom.nextInt(7);

            double angle =
                    Math.toRadians(
                            secureRandom.nextInt(31)
                                    - 15
                    );

            graphics.rotate(
                    angle,
                    x,
                    y
            );

            graphics.drawString(
                    String.valueOf(character),
                    x,
                    y
            );

            graphics.rotate(
                    -angle,
                    x,
                    y
            );
        }
    }

    private Color randomDarkColor() {
        return new Color(
                secureRandom.nextInt(100),
                secureRandom.nextInt(100),
                secureRandom.nextInt(100)
        );
    }

    private Color randomLightColor() {
        return new Color(
                120 + secureRandom.nextInt(100),
                120 + secureRandom.nextInt(100),
                120 + secureRandom.nextInt(100)
        );
    }

    private String toBase64(
            BufferedImage image
    ) {
        try {
            ByteArrayOutputStream output =
                    new ByteArrayOutputStream();

            ImageIO.write(
                    image,
                    "png",
                    output
            );

            String base64 =
                    Base64.getEncoder()
                            .encodeToString(
                                    output.toByteArray()
                            );

            return "data:image/png;base64,"
                    + base64;

        } catch (Exception exception) {
            throw new IllegalStateException(
                    "Failed to generate captcha image",
                    exception
            );
        }
    }
}
