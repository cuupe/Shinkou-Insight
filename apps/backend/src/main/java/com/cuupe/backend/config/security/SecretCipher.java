package com.cuupe.backend.config.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

@Component
public class SecretCipher {
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int IV_LENGTH = 12;
    private static final int TAG_LENGTH = 128;
    private final SecretKeySpec key;
    private final SecureRandom random = new SecureRandom();

    public SecretCipher(
            @Value("${shinkou.security.encryption-key}") String encodedKey,
            @Value("${shinkou.security.environment:development}") String environment) {
        byte[] bytes;
        if (encodedKey == null || encodedKey.isBlank()) {
            if ("production".equalsIgnoreCase(environment)) {
                throw new IllegalStateException("生产环境必须配置 SHINKOU_ENCRYPTION_KEY");
            }
            bytes = new byte[32];
            new SecureRandom().nextBytes(bytes);
            System.err.println("SHINKOU_ENCRYPTION_KEY 未配置，仅使用临时开发密钥；重启后已保存凭证将无法解密");
        } else {
            bytes = Base64.getDecoder().decode(encodedKey);
        }
        if (bytes.length != 32) throw new IllegalArgumentException("encryption-key 必须是 Base64 编码的 32 字节密钥");
        this.key = new SecretKeySpec(bytes, "AES");
    }

    public String encrypt(String value) {
        try {
            byte[] iv = new byte[IV_LENGTH]; random.nextBytes(iv);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(TAG_LENGTH, iv));
            byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(ByteBuffer.allocate(iv.length + encrypted.length).put(iv).put(encrypted).array());
        } catch (Exception exception) { throw new IllegalStateException("无法加密配置凭证", exception); }
    }

    public String decrypt(String value) {
        try {
            byte[] packed = Base64.getDecoder().decode(value);
            ByteBuffer buffer = ByteBuffer.wrap(packed);
            byte[] iv = new byte[IV_LENGTH];
            buffer.get(iv);
            byte[] encrypted = new byte[buffer.remaining()];
            buffer.get(encrypted);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(TAG_LENGTH, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception exception) { throw new IllegalStateException("无法解密配置凭证", exception); }
    }
}
