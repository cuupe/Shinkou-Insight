package com.cuupe.backend.utils;

import java.security.SecureRandom;

/**
 * 雪花算法 ID 生成器（单节点版）。
 * 生成 64 位正整数：41 位时间戳 + 10 位机器位 + 12 位序列号，
 * 适合 bigint 主键，避免依赖数据库自增序列。
 */
public final class SnowflakeIdGenerator {

    private static final long EPOCH = 1735689600000L; // 2025-01-01T00:00:00Z
    private static final long WORKER_ID_BITS = 10L;
    private static final long SEQUENCE_BITS = 12L;
    private static final long MAX_SEQUENCE = (1L << SEQUENCE_BITS) - 1;
    private static final long WORKER_ID_SHIFT = SEQUENCE_BITS;
    private static final long TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS;

    private static final long WORKER_ID;
    private static long lastTimestamp = -1L;
    private static long sequence = 0L;

    static {
        // 单机部署下随机分配机器位，避免多实例冲突
        WORKER_ID = new SecureRandom().nextInt(1 << WORKER_ID_BITS);
    }

    private SnowflakeIdGenerator() {
    }

    public static synchronized long nextId() {
        long timestamp = System.currentTimeMillis();
        if (timestamp < lastTimestamp) {
            // 时钟回拨时直接使用上次时间戳，保证单调递增
            timestamp = lastTimestamp;
        }
        if (timestamp == lastTimestamp) {
            sequence = (sequence + 1) & MAX_SEQUENCE;
            if (sequence == 0) {
                timestamp = waitNextMillis(lastTimestamp);
            }
        } else {
            sequence = 0L;
        }
        lastTimestamp = timestamp;
        return ((timestamp - EPOCH) << TIMESTAMP_SHIFT)
                | (WORKER_ID << WORKER_ID_SHIFT)
                | sequence;
    }

    private static long waitNextMillis(long current) {
        long timestamp = System.currentTimeMillis();
        while (timestamp <= current) {
            timestamp = System.currentTimeMillis();
        }
        return timestamp;
    }
}
