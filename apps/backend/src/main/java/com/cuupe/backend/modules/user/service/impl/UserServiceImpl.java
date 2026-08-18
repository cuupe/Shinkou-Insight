package com.cuupe.backend.modules.user.service.impl;

import com.cuupe.backend.modules.user.entity.User;
import com.cuupe.backend.modules.user.mapper.UserMapper;
import com.cuupe.backend.modules.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.jspecify.annotations.NonNull;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService, UserDetailsService {
    private final UserMapper userMapper;

    @Override
    public User findUserByPhoneNumber(String phoneNumber) {
        return userMapper.findUserByPhoneNumber(phoneNumber);
    }

    @Override
    public UserDetails loadUserByUsername(@NonNull String phoneNumber)
            throws UsernameNotFoundException {
        UserDetails userDetails = userMapper.findAuthUserByPhoneNumber(phoneNumber);
        if (userDetails == null) {
            throw new UsernameNotFoundException("手机号或密码错误");
        }
        return userDetails;
    }
}
