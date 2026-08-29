package com.cuupe.backend.modules.storage;

import io.minio.BucketExistsArgs;
import io.minio.GetObjectArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.InputStream;

@Service
@RequiredArgsConstructor
public class ObjectStorageService {
    private final MinioClient minioClient;

    @Value("${shinkou.storage.minio.bucket:shinkou-files}")
    private String bucket;

    public String put(String key, InputStream input, long size, String contentType) throws Exception {
        ensureBucket();
        minioClient.putObject(PutObjectArgs.builder()
                .bucket(bucket)
                .object(key)
                .stream(input, size, -1L)
                .contentType(contentType == null ? "application/octet-stream" : contentType)
                .build());
        return key;
    }

    public InputStream open(String key) throws Exception {
        return minioClient.getObject(GetObjectArgs.builder().bucket(bucket).object(key).build());
    }

    public void remove(String key) throws Exception {
        if (key == null || key.isBlank()) return;
        minioClient.removeObject(RemoveObjectArgs.builder().bucket(bucket).object(key).build());
    }

    private void ensureBucket() throws Exception {
        if (!minioClient.bucketExists(BucketExistsArgs.builder().bucket(bucket).build())) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
        }
    }
}
