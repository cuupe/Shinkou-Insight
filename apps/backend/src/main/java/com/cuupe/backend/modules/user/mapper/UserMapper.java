package com.cuupe.backend.modules.user.mapper;

import com.cuupe.backend.modules.user.entity.User;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.springframework.security.core.userdetails.UserDetails;

@Mapper
public interface UserMapper {
    User findUserByPhoneNumber(
            @Param("phoneNumber") String phoneNumber
    );

    UserDetails findAuthUserByPhoneNumber(
            @Param("phoneNumber") String phoneNumber
    );

}
