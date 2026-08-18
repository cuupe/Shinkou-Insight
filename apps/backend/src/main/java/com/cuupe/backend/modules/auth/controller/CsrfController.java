package com.cuupe.backend.modules.auth.controller;

import com.cuupe.backend.common.Result;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
public class CsrfController {
    @GetMapping("/csrf")
    public Result<CsrfToken> csrf(CsrfToken csrfToken) {
        return Result.success(csrfToken);
    }
}
