package com.cuupe.backend.config;

import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class StorageConfig {
    @Bean
    public MinioClient minioClient(
            @Value("${shinkou.storage.minio.endpoint:http://localhost:9000}") String endpoint,
            @Value("${shinkou.storage.minio.access-key:shinkou_minio}") String accessKey,
            @Value("${shinkou.storage.minio.secret-key:shinkou_minio_password}") String secretKey
    ) {
        return MinioClient.builder().endpoint(endpoint).credentials(accessKey, secretKey).build();
    }
}
