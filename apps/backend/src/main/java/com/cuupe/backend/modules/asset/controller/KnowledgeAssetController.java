package com.cuupe.backend.modules.asset.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import com.cuupe.backend.modules.asset.mapper.KnowledgeAssetMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.storage.ObjectStorageService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/assets")
@RequiredArgsConstructor
public class KnowledgeAssetController {
    private final KnowledgeAssetMapper assetMapper;
    private final NotificationService notificationService;
    private final ObjectStorageService objectStorageService;
    private final AiIndexingClient aiIndexingClient;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final AuditLogService auditLogService;

    @GetMapping public Result<List<KnowledgeAsset>> list(@PathVariable Long projectId, Authentication auth) { return Result.success(assetMapper.findByProject(projectId, userId(auth))); }
    @GetMapping("/{assetId}") public Result<KnowledgeAsset> detail(@PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) { return Result.success(required(projectId, assetId, auth)); }

    @PostMapping(consumes = "multipart/form-data")
    public Result<KnowledgeAsset> upload(@PathVariable Long workspaceId, @PathVariable Long projectId, @RequestPart("file") MultipartFile file, @RequestParam(required=false) String name, @RequestParam(required=false) String language, Authentication auth) throws Exception {
        if (file.isEmpty()) throw ApiException.badRequest("EMPTY_FILE", "上传文件不能为空");
        KnowledgeAsset asset = new KnowledgeAsset();
        asset.setProjectId(projectId); asset.setCreatedBy(userId(auth)); asset.setName(name == null || name.isBlank() ? file.getOriginalFilename() : name.trim());
        asset.setAssetType(typeOf(file.getOriginalFilename())); asset.setMimeType(file.getContentType()); asset.setLanguage(language); asset.setFileSize(file.getSize()); asset.setChecksum(hex(MessageDigest.getInstance("SHA-256").digest(file.getBytes())));
        String storageKey = "workspaces/" + workspaceId + "/projects/" + projectId + "/assets/" + asset.getChecksum() + "/" + safeFileName(file.getOriginalFilename());
        try (var input = file.getInputStream()) {
            objectStorageService.put(storageKey, input, file.getSize(), file.getContentType());
        }
        asset.setStorageKey(storageKey);
        if (file.getContentType() != null && (file.getContentType().startsWith("text/") || file.getOriginalFilename().toLowerCase().endsWith(".md"))) asset.setContent(new String(file.getBytes(), StandardCharsets.UTF_8));
        try {
            assetMapper.insert(asset); createChunks(asset);
            assetMapper.markIndexing(asset.getId(), projectId);
            KnowledgeAsset indexedAsset = asset;
            Long workspace = workspaceId;
            Long user = userId(auth);
            Map<String, Object> runtimeEmbedding = runtimeConfigResolver.resolveEmbeddingPayload(projectId, user, null);
            Thread.startVirtualThread(() -> {
                try {
                    aiIndexingClient.index(indexedAsset, workspace, user, runtimeEmbedding);
                    assetMapper.markIndexed(indexedAsset.getId(), indexedAsset.getProjectId());
                } catch (Exception exception) {
                    assetMapper.markIndexFailed(indexedAsset.getId(), indexedAsset.getProjectId(), exception.getMessage());
                }
            });
        } catch (RuntimeException exception) {
            try { objectStorageService.remove(storageKey); } catch (Exception ignored) { }
            throw exception;
        }
        notificationService.create(workspaceId, userId(auth), projectId, "knowledge", "知识库资料已上传", "“" + asset.getName() + "”正在建立索引。", "project-assets");
        auditLogService.record(workspaceId, projectId, userId(auth), "ASSET_UPLOADED", "ASSET", asset.getId(), Map.of("name", asset.getName() == null ? "" : asset.getName(), "size", asset.getFileSize()));
        return Result.success(required(projectId, asset.getId(), auth));
    }
    @DeleteMapping("/{assetId}") public Result<Void> remove(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) { Long user=userId(auth); if (assetMapper.markDeleted(assetId, projectId, user) == 0) throw notFound(); auditLogService.record(workspaceId, projectId, user, "ASSET_DELETED", "ASSET", assetId); return Result.success(); }
    @PostMapping("/{assetId}/reindex") public Result<KnowledgeAsset> reindex(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) { Long user=userId(auth); if (assetMapper.resetIndex(assetId, projectId, user) == 0) throw notFound(); KnowledgeAsset asset=required(projectId,assetId,auth); createChunks(asset); assetMapper.markIndexing(assetId, projectId); Map<String, Object> runtimeEmbedding=runtimeConfigResolver.resolveEmbeddingPayload(projectId, user, null); Thread.startVirtualThread(() -> { try { aiIndexingClient.index(asset, workspaceId, user, runtimeEmbedding); assetMapper.markIndexed(assetId, projectId); } catch (Exception exception) { assetMapper.markIndexFailed(assetId, projectId, exception.getMessage()); } }); auditLogService.record(workspaceId, projectId, user, "ASSET_REINDEX_REQUESTED", "ASSET", assetId); return Result.success(required(projectId, assetId, auth)); }
    @GetMapping("/{assetId}/chunks") public Result<List<Map<String,Object>>> chunks(@PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) { required(projectId,assetId,auth); return Result.success(assetMapper.findChunks(assetId,projectId,userId(auth))); }
    @GetMapping("/{assetId}/content") public Result<String> content(@PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) { KnowledgeAsset asset=required(projectId,assetId,auth); return Result.success(asset.getContent() == null ? "" : asset.getContent()); }

    private KnowledgeAsset required(Long projectId, Long assetId, Authentication auth) { KnowledgeAsset asset=assetMapper.findById(assetId, projectId, userId(auth)); if(asset==null) throw notFound(); return asset; }
    private Long userId(Authentication auth) { Object principal=auth.getPrincipal(); if(principal instanceof UserLoginByPassword user && user.getId()!=null) return user.getId(); throw new IllegalStateException("当前会话缺少用户信息"); }
    private ApiException notFound() { return new ApiException(org.springframework.http.HttpStatus.NOT_FOUND,"ASSET_NOT_FOUND","资料不存在或无权访问"); }
    private String typeOf(String filename) { if(filename==null) return "FILE"; int dot=filename.lastIndexOf('.'); return dot<0 ? "FILE" : filename.substring(dot+1).toUpperCase(); }
    private String hex(byte[] bytes) { StringBuilder result=new StringBuilder(); for(byte value:bytes) result.append(String.format("%02x",value)); return result.toString(); }
    private String safeFileName(String value) { String name=value==null||value.isBlank()?"file":value.replaceAll("[\\r\\n\\\\/]", "_").trim(); return name.length()<=255?name:name.substring(0,255); }
    private void createChunks(KnowledgeAsset asset) { assetMapper.deleteChunks(asset.getId()); if (asset.getContent() == null || asset.getContent().isBlank()) return; int size=1200; for(int start=0,index=0;start<asset.getContent().length();start+=size,index++) assetMapper.insertChunk(asset.getId(),index,asset.getContent().substring(start,Math.min(start+size,asset.getContent().length()))); }
}
