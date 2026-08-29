package com.cuupe.backend.modules.user.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class User {
    private Long id;
    private String userName;
    private String phoneNumber;
    @JsonIgnore
    private String password;
    private LocalDateTime loginAt;
    private LocalDateTime createAt;
    private Integer status;
    private String email;
    private String timezone;
    private String notificationPreferences;
}
