package com.cuupe.backend.modules.user.service;

import com.cuupe.backend.modules.user.entity.User;
import org.springframework.stereotype.Service;

@Service
public interface UserService {
    User findUserByPhoneNumber(String phoneNumber);

}
