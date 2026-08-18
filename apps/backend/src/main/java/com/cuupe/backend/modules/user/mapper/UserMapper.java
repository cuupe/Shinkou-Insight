package com.cuupe.backend.modules.user.mapper;

import com.cuupe.backend.modules.user.entity.User;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;

@Mapper
public interface UserMapper {
    User findUserByPhoneNumber(
            @Param("phoneNumber") String phoneNumber
    );

    UserLoginByPassword findAuthUserByPhoneNumber(
            @Param("phoneNumber") String phoneNumber
    );

    boolean existPhoneNumber(
            @Param("phoneNumber") String phoneNumber
    );

    void createNewUser(
            @Param("userName") String userName,
            @Param("phoneNumber") String phoneNumber,
            @Param("password") String password,
            @Param("createAt") LocalDateTime createAt,
            @Param("status") Integer status
            );

}
