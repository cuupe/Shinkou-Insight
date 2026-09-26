package com.cuupe.backend.modules.storage.service;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.storage.dto.StorageQuotaResponse;
import com.cuupe.backend.modules.storage.mapper.StorageQuotaMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class StorageQuotaService {
    public static final long MAX_SINGLE_FILE_BYTES = 256L * 1024 * 1024;
    public static final long MAX_STORAGE_BYTES = 512L * 1024 * 1024;

    private final StorageQuotaMapper mapper;

    public void validateFileSize(long bytes) {
        if (bytes <= 0) throw ApiException.badRequest("EMPTY_FILE", "文件不能为空");
        if (bytes >= MAX_SINGLE_FILE_BYTES) {
            throw ApiException.badRequest("FILE_TOO_LARGE", "单个文件必须小于 256 MB");
        }
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void reserve(Long userId, long bytes) {
        validateFileSize(bytes);
        mapper.ensureUser(userId);
        long tracked = value(mapper.lockUsedBytes(userId));
        long actual = value(mapper.findFileBytes(userId)) + value(mapper.findKnowledgeBytes(userId));
        long used = Math.max(tracked, actual);
        if (used > MAX_STORAGE_BYTES || bytes > MAX_STORAGE_BYTES - used) {
            throw ApiException.badRequest("STORAGE_QUOTA_EXCEEDED", "存储空间不足：每个用户最多使用 512 MB");
        }
        mapper.updateUsedBytes(userId, used + bytes);
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void release(Long userId, long bytes) {
        if (bytes <= 0) return;
        mapper.ensureUser(userId);
        long tracked = value(mapper.lockUsedBytes(userId));
        long actual = value(mapper.findFileBytes(userId)) + value(mapper.findKnowledgeBytes(userId));
        long used = Math.max(tracked, actual);
        mapper.updateUsedBytes(userId, Math.max(0L, used - bytes));
    }

    public StorageQuotaResponse snapshot(Long userId) {
        mapper.ensureUser(userId);
        long fileBytes = value(mapper.findFileBytes(userId));
        long knowledgeBytes = value(mapper.findKnowledgeBytes(userId));
        long usedBytes = Math.min(MAX_STORAGE_BYTES, fileBytes + knowledgeBytes);
        long remainingBytes = Math.max(0L, MAX_STORAGE_BYTES - usedBytes);
        int usagePercent = (int) Math.min(100L, Math.ceil(usedBytes * 100d / MAX_STORAGE_BYTES));
        return new StorageQuotaResponse(
                fileBytes,
                knowledgeBytes,
                usedBytes,
                MAX_STORAGE_BYTES,
                remainingBytes,
                usagePercent,
                MAX_SINGLE_FILE_BYTES
        );
    }

    private long value(Long value) {
        return value == null ? 0L : Math.max(0L, value);
    }
}
