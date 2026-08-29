package com.cuupe.backend.modules.settings.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.config.security.SecretCipher;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.settings.dto.ModelConfigRequest;
import com.cuupe.backend.modules.settings.dto.ToolConfigRequest;
import com.cuupe.backend.modules.settings.entity.ModelConfig;
import com.cuupe.backend.modules.settings.entity.ToolConfig;
import com.cuupe.backend.modules.settings.mapper.ModelConfigMapper;
import com.cuupe.backend.modules.settings.mapper.ToolConfigMapper;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/settings")
@RequiredArgsConstructor
public class ProjectSettingsController {
    private final ProjectMapper projectMapper;
    private final ModelConfigMapper modelMapper;
    private final ToolConfigMapper toolMapper;
    private final SecretCipher cipher;

    @GetMapping("/models") public Result<List<ModelConfig>> models(@PathVariable Long projectId, Authentication auth) { return Result.success(modelMapper.findByProject(projectId, userId(auth))); }
    @PostMapping("/models") public Result<ModelConfig> createModel(@PathVariable Long workspaceId, @PathVariable Long projectId, @Valid @RequestBody ModelConfigRequest request, Authentication auth) {
        Long userId=userId(auth); writeAccess(workspaceId, projectId, userId); ModelConfig config=new ModelConfig(); config.setProjectId(projectId); config.setCreatedBy(userId); config.setName(request.name().trim()); config.setProvider(request.provider().trim()); config.setModelId(request.modelId().trim()); config.setEndpoint(request.endpoint().trim()); config.setAuthType(defaultValue(request.authType(), "API_KEY")); config.setCredentialCiphertext(encrypt(request.credential())); config.setConfig(defaultValue(request.config(), "{}")); config.setEnabled(request.enabled()==null || request.enabled()); modelMapper.insert(config); return Result.success(modelMapper.findById(config.getId(), projectId, userId));
    }
    @PatchMapping("/models/{id}") public Result<ModelConfig> updateModel(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long id,@Valid @RequestBody ModelConfigRequest request,Authentication auth) { Long userId=userId(auth); writeAccess(workspaceId,projectId,userId); ModelConfig config=requiredModel(id,projectId,userId); config.setName(request.name().trim()); config.setProvider(request.provider().trim()); config.setModelId(request.modelId().trim()); config.setEndpoint(request.endpoint().trim()); config.setAuthType(defaultValue(request.authType(),config.getAuthType())); if(request.credential()!=null&&!request.credential().isBlank()) config.setCredentialCiphertext(cipher.encrypt(request.credential())); config.setConfig(defaultValue(request.config(),config.getConfig())); if(request.enabled()!=null) config.setEnabled(request.enabled()); modelMapper.update(config); return Result.success(modelMapper.findById(id,projectId,userId)); }
    @DeleteMapping("/models/{id}") public Result<Void> deleteModel(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long id,Authentication auth) { Long userId=userId(auth); writeAccess(workspaceId,projectId,userId); modelMapper.delete(id,projectId); return Result.success(); }

    @GetMapping("/tools") public Result<List<ToolConfig>> tools(@PathVariable Long projectId, Authentication auth) { return Result.success(toolMapper.findByProject(projectId,userId(auth))); }
    @PostMapping("/tools") public Result<ToolConfig> createTool(@PathVariable Long workspaceId,@PathVariable Long projectId,@Valid @RequestBody ToolConfigRequest request,Authentication auth) { Long userId=userId(auth); writeAccess(workspaceId,projectId,userId); ToolConfig config=new ToolConfig(); config.setProjectId(projectId); config.setCreatedBy(userId); config.setName(request.name().trim()); config.setEndpoint(request.endpoint().trim()); config.setConnectorType(defaultValue(request.connectorType(),"REST_API")); config.setAuthType(defaultValue(request.authType(),"API_KEY")); config.setCredentialCiphertext(encrypt(request.credential())); config.setConfig(defaultValue(request.config(),"{}")); config.setEnabled(request.enabled()==null||request.enabled()); toolMapper.insert(config); return Result.success(toolMapper.findById(config.getId(),projectId,userId)); }
    @PatchMapping("/tools/{id}") public Result<ToolConfig> updateTool(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long id,@Valid @RequestBody ToolConfigRequest request,Authentication auth) { Long userId=userId(auth); writeAccess(workspaceId,projectId,userId); ToolConfig config=requiredTool(id,projectId,userId); config.setName(request.name().trim()); config.setEndpoint(request.endpoint().trim()); config.setConnectorType(defaultValue(request.connectorType(),config.getConnectorType())); config.setAuthType(defaultValue(request.authType(),config.getAuthType())); if(request.credential()!=null&&!request.credential().isBlank()) config.setCredentialCiphertext(cipher.encrypt(request.credential())); config.setConfig(defaultValue(request.config(),config.getConfig())); if(request.enabled()!=null) config.setEnabled(request.enabled()); toolMapper.update(config); return Result.success(toolMapper.findById(id,projectId,userId)); }
    @DeleteMapping("/tools/{id}") public Result<Void> deleteTool(@PathVariable Long workspaceId,@PathVariable Long projectId,@PathVariable Long id,Authentication auth) { Long userId=userId(auth); writeAccess(workspaceId,projectId,userId); toolMapper.delete(id,projectId); return Result.success(); }

    private Long userId(Authentication auth) { Object principal=auth.getPrincipal(); if(principal instanceof UserLoginByPassword user && user.getId()!=null) return user.getId(); throw new IllegalStateException("当前会话缺少用户信息"); }
    private void writeAccess(Long workspaceId,Long projectId,Long userId) { if(!projectMapper.hasWriteAccess(workspaceId,projectId,userId)) throw new ApiException(HttpStatus.FORBIDDEN,"PROJECT_SETTINGS_FORBIDDEN","只有项目创建者或管理员可以修改项目设置"); }
    private ModelConfig requiredModel(Long id,Long projectId,Long userId) { ModelConfig config=modelMapper.findById(id,projectId,userId); if(config==null) throw new ApiException(HttpStatus.NOT_FOUND,"MODEL_CONFIG_NOT_FOUND","模型配置不存在或无权访问"); return config; }
    private ToolConfig requiredTool(Long id,Long projectId,Long userId) { ToolConfig config=toolMapper.findById(id,projectId,userId); if(config==null) throw new ApiException(HttpStatus.NOT_FOUND,"TOOL_CONFIG_NOT_FOUND","工具配置不存在或无权访问"); return config; }
    private String encrypt(String value) { return value==null||value.isBlank()?null:cipher.encrypt(value); }
    private String defaultValue(String value,String fallback) { return value==null||value.isBlank()?fallback:value; }
}