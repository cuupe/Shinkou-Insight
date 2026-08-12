package com.cuupe.backend.modules.auth.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.modules.auth.dto.response.CaptchaResponse;
import com.cuupe.backend.modules.auth.service.CaptchaService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class CaptchaController {
    private final CaptchaService captchaService;

    @GetMapping("/captcha")
    public Result<CaptchaResponse> captcha(){
        var res = captchaService.generate();

        return Result.success(new CaptchaResponse(
                res.captchaId(),
                res.imgUrl()
        ));
    }

}
