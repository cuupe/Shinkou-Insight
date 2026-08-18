package com.cuupe.backend.modules.auth.enums;

public enum UserStatus {
    NORMAL_STATUS,
    BANNED_STATUS;

    public static int NORMAL_STATUS(){
        return 0;
    }

    public static int BANNED_STATUS(){
        return 1;
    }
}
