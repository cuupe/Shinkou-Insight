package com.cuupe.backend.modules.storage.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.storage.dto.StorageQuotaResponse;
import com.cuupe.backend.modules.storage.service.StorageQuotaService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/storage")
@RequiredArgsConstructor
public class StorageQuotaController {
    private final ProjectMapper projectMapper;
    private final StorageQuotaService storageQuotaService;

    @GetMapping("/quota")
    public Result<StorageQuotaResponse> quota(
            @PathVariable Long workspaceId,
            @PathVariable Long projectId,
            Authentication authentication
    ) {
        Long userId = userId(authentication);
        if (projectMapper.findAccessibleById(workspaceId, projectId, userId) == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在或无权访问");
        }
        return Result.success(storageQuotaService.snapshot(userId));
    }

    private Long userId(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        if (principal instanceof UserLoginByPassword user && user.getId() != null) return user.getId();
        throw new IllegalStateException("当前会话缺少用户信息");
    }
}
