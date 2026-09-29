package com.cuupe.backend.modules.asset.controller;

import com.cuupe.backend.common.Result;
import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.audit.service.AuditLogService;
import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import com.cuupe.backend.modules.asset.mapper.KnowledgeAssetMapper;
import com.cuupe.backend.modules.asset.service.AssetIndexingService;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.ai.RuntimeConfigResolver;
import com.cuupe.backend.modules.notification.service.NotificationService;
import com.cuupe.backend.modules.project.entity.Project;
import com.cuupe.backend.modules.project.mapper.ProjectMapper;
import com.cuupe.backend.modules.storage.ObjectStorageService;
import com.cuupe.backend.modules.storage.service.StorageQuotaService;
import com.cuupe.backend.modules.user.security.UserLoginByPassword;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/workspaces/{workspaceId}/projects/{projectId}/assets")
@RequiredArgsConstructor
public class KnowledgeAssetController {
    private static final int TEXT_PREVIEW_LIMIT = 2 * 1024 * 1024;

    private final KnowledgeAssetMapper assetMapper;
    private final NotificationService notificationService;
    private final ObjectStorageService objectStorageService;
    private final AiIndexingClient aiIndexingClient;
    private final RuntimeConfigResolver runtimeConfigResolver;
    private final ProjectMapper projectMapper;
    private final AuditLogService auditLogService;
    private final StorageQuotaService storageQuotaService;
    private final AssetIndexingService assetIndexingService;

    @GetMapping public Result<List<KnowledgeAsset>> list(@PathVariable Long projectId, Authentication auth) { return Result.success(assetMapper.findByProject(projectId, userId(auth))); }
    @GetMapping("/{assetId}") public Result<KnowledgeAsset> detail(@PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) { return Result.success(required(projectId, assetId, auth)); }

    @PostMapping(consumes = "multipart/form-data")
    @Transactional(rollbackFor = Exception.class)
    public Result<KnowledgeAsset> upload(@PathVariable Long workspaceId, @PathVariable Long projectId, @RequestPart("file") MultipartFile file, @RequestParam(required=false) String name, @RequestParam(required=false) String language, @RequestParam(required=false) String sourceUrl, Authentication auth) throws Exception {
        if (file.isEmpty()) throw ApiException.badRequest("EMPTY_FILE", "上传文件不能为空");
        Long currentUserId = userId(auth);
        storageQuotaService.validateFileSize(file.getSize());
        KnowledgeAsset asset = new KnowledgeAsset();
        asset.setProjectId(projectId); asset.setCreatedBy(currentUserId); asset.setName(name == null || name.isBlank() ? file.getOriginalFilename() : name.trim());
        asset.setAssetType(typeOf(file.getOriginalFilename())); asset.setMimeType(file.getContentType()); asset.setLanguage(language); asset.setFileSize(file.getSize()); asset.setChecksum(hex(MessageDigest.getInstance("SHA-256").digest(file.getBytes())));
        String normalizedSourceUrl = sourceUrl == null ? "" : sourceUrl.trim();
        asset.setSourceUrl(normalizedSourceUrl.isBlank() ? null : normalizedSourceUrl);
        if (!normalizedSourceUrl.isBlank()) {
            KnowledgeAsset sourceMatch = assetMapper.findByProjectAndSourceUrl(projectId, normalizedSourceUrl, currentUserId);
            if (sourceMatch != null) return Result.success(sourceMatch);
            Map<String, Object> validation;
            try {
                validation = aiIndexingClient.validateWebSource(
                        normalizedSourceUrl,
                        asset.getName(),
                        new String(file.getBytes(), StandardCharsets.UTF_8)
                );
            } catch (Exception exception) {
                throw new ApiException(HttpStatus.BAD_GATEWAY, "SOURCE_VALIDATION_UNAVAILABLE", "暂时无法验证引用来源，请稍后重试");
            }
            if (!Boolean.TRUE.equals(validation.get("valid"))) {
                String reason = String.valueOf(validation.getOrDefault("reason", "来源页面无效"));
                throw ApiException.badRequest("INVALID_SOURCE", "引用来源未通过验证：" + reason);
            }
        }
        KnowledgeAsset existing = assetMapper.findByProjectAndChecksum(projectId, asset.getChecksum(), currentUserId);
        if (existing != null) return Result.success(existing);
        storageQuotaService.reserve(currentUserId, file.getSize());
        String storageKey = "workspaces/" + workspaceId + "/projects/" + projectId + "/assets/" + asset.getChecksum() + "/" + safeFileName(file.getOriginalFilename());
        try (var input = file.getInputStream()) {
            objectStorageService.put(storageKey, input, file.getSize(), file.getContentType());
        }
        asset.setStorageKey(storageKey);
        try {
            assetMapper.insert(asset);
            assetMapper.markIndexing(asset.getId(), projectId);
            KnowledgeAsset indexedAsset = asset;
            Long workspace = workspaceId;
            Long user = userId(auth);
            Map<String, Object> runtimeEmbedding = runtimeConfigResolver.resolveEmbeddingPayload(workspaceId, projectId, user, null);
            Project project = projectMapper.findAccessibleById(workspaceId, projectId, user);
            String chunkingConfig = project == null ? null : project.getChunkingConfig();
            assetIndexingService.schedule(indexedAsset, workspace, user, runtimeEmbedding, chunkingConfig);
        } catch (RuntimeException exception) {
            KnowledgeAsset duplicate = assetMapper.findByProjectAndChecksum(projectId, asset.getChecksum(), currentUserId);
            if (duplicate != null) {
                storageQuotaService.release(currentUserId, asset.getFileSize());
                try { objectStorageService.remove(storageKey); } catch (Exception ignored) { }
                return Result.success(duplicate);
            }
            try { objectStorageService.remove(storageKey); } catch (Exception ignored) { }
            throw exception;
        }
        notificationService.create(workspaceId, userId(auth), projectId, "knowledge", "知识库资料已上传", "“" + asset.getName() + "”正在建立索引。", "project-assets");
        auditLogService.record(workspaceId, projectId, userId(auth), "ASSET_UPLOADED", "ASSET", asset.getId(), Map.of("name", asset.getName() == null ? "" : asset.getName(), "size", asset.getFileSize()));
        return Result.success(required(projectId, asset.getId(), auth));
    }
    @DeleteMapping("/{assetId}")
    @Transactional(rollbackFor = Exception.class)
    public Result<Void> remove(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) {
        Long user = userId(auth);
        KnowledgeAsset asset = required(projectId, assetId, auth);
        if (assetMapper.markDeleted(assetId, projectId, user) == 0) throw notFound();
        storageQuotaService.release(user, asset.getFileSize() == null ? 0L : asset.getFileSize());
        auditLogService.record(workspaceId, projectId, user, "ASSET_DELETED", "ASSET", assetId);
        return Result.success();
    }
    @PostMapping("/{assetId}/reindex")
    @Transactional(rollbackFor = Exception.class)
    public Result<KnowledgeAsset> reindex(@PathVariable Long workspaceId, @PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) {
        Long user = userId(auth);
        if (assetMapper.resetIndex(assetId, projectId, user) == 0) throw notFound();
        KnowledgeAsset asset = required(projectId, assetId, auth);
        assetMapper.markIndexing(assetId, projectId);
        Map<String, Object> runtimeEmbedding = runtimeConfigResolver.resolveEmbeddingPayload(workspaceId, projectId, user, null);
        Project project = projectMapper.findAccessibleById(workspaceId, projectId, user);
        // The indexer replaces chunks only after parsing and embedding succeed.
        assetIndexingService.schedule(asset, workspaceId, user, runtimeEmbedding,
                project == null ? null : project.getChunkingConfig());
        auditLogService.record(workspaceId, projectId, user, "ASSET_REINDEX_REQUESTED", "ASSET", assetId);
        return Result.success(required(projectId, assetId, auth));
    }
    @GetMapping("/{assetId}/chunks")
    public Result<List<Map<String,Object>>> chunks(
            @PathVariable Long projectId,
            @PathVariable Long assetId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "30") int pageSize,
            @RequestParam(required = false) Long chunkId,
            @RequestParam(required = false) Integer pageNumber,
            Authentication auth) {
        KnowledgeAsset asset = required(projectId, assetId, auth);
        int safePageSize = Math.max(1, Math.min(pageSize, 100));
        int pageCount = Math.max(1, (int) Math.ceil((asset.getChunkCount() == null ? 0 : asset.getChunkCount()) / (double) safePageSize));
        int safePage = Math.max(1, Math.min(page, pageCount));
        int offset = Math.multiplyExact(safePage - 1, safePageSize);
        return Result.success(assetMapper.findChunks(assetId, projectId, userId(auth), offset, safePageSize, chunkId, pageNumber));
    }
    @GetMapping("/{assetId}/content")
    public Result<String> content(@PathVariable Long projectId, @PathVariable Long assetId, Authentication auth) throws Exception {
        KnowledgeAsset asset = required(projectId, assetId, auth);
        if (asset.getStorageKey() == null || asset.getStorageKey().isBlank() || !isTextAsset(asset)) {
            return Result.success("");
        }
        try (var input = objectStorageService.open(asset.getStorageKey())) {
            byte[] bytes = input.readNBytes(TEXT_PREVIEW_LIMIT + 4);
            boolean truncated = bytes.length > TEXT_PREVIEW_LIMIT;
            String content = decodeText(bytes);
            if (truncated) {
                content = content.substring(0, Math.min(content.length(), TEXT_PREVIEW_LIMIT)) + "\n\n[预览已截断]";
            }
            return Result.success(content);
        }
    }

    private KnowledgeAsset required(Long projectId, Long assetId, Authentication auth) { KnowledgeAsset asset=assetMapper.findById(assetId, projectId, userId(auth)); if(asset==null) throw notFound(); return asset; }
    private Long userId(Authentication auth) { Object principal=auth.getPrincipal(); if(principal instanceof UserLoginByPassword user && user.getId()!=null) return user.getId(); throw new IllegalStateException("当前会话缺少用户信息"); }
    private ApiException notFound() { return new ApiException(org.springframework.http.HttpStatus.NOT_FOUND,"ASSET_NOT_FOUND","资料不存在或无权访问"); }
    private String typeOf(String filename) { if(filename==null) return "FILE"; int dot=filename.lastIndexOf('.'); return dot<0 ? "FILE" : filename.substring(dot+1).toUpperCase(); }
    private boolean isTextAsset(KnowledgeAsset asset) { return asset.getMimeType() != null && asset.getMimeType().toLowerCase().startsWith("text/") || "MD".equalsIgnoreCase(asset.getAssetType()) || "TXT".equalsIgnoreCase(asset.getAssetType()); }
    private String hex(byte[] bytes) { StringBuilder result=new StringBuilder(); for(byte value:bytes) result.append(String.format("%02x",value)); return result.toString(); }
    private String safeFileName(String value) { String name=value==null||value.isBlank()?"file":value.replaceAll("[\\r\\n\\\\/]", "_").trim(); return name.length()<=255?name:name.substring(0,255); }

    private String decodeText(byte[] bytes) {
        int offset = 0;
        Charset charset;
        if (startsWith(bytes, 0x00, 0x00, 0xFE, 0xFF)) {
            charset = Charset.forName("UTF-32BE"); offset = 4;
        } else if (startsWith(bytes, 0xFF, 0xFE, 0x00, 0x00)) {
            charset = Charset.forName("UTF-32LE"); offset = 4;
        } else if (startsWith(bytes, 0xEF, 0xBB, 0xBF)) {
            charset = StandardCharsets.UTF_8; offset = 3;
        } else if (startsWith(bytes, 0xFE, 0xFF)) {
            charset = StandardCharsets.UTF_16BE; offset = 2;
        } else if (startsWith(bytes, 0xFF, 0xFE)) {
            charset = StandardCharsets.UTF_16LE; offset = 2;
        } else {
            Charset unmarkedUtf16 = detectUnmarkedUtf16(bytes);
            if (unmarkedUtf16 != null) charset = unmarkedUtf16;
            else {
                try { return decodeStrict(bytes, StandardCharsets.UTF_8, 0); }
                catch (CharacterCodingException ignored) { charset = Charset.forName("GB18030"); }
            }
        }
        try { return decodeStrict(bytes, charset, offset); }
        catch (CharacterCodingException ignored) { return new String(bytes, offset, bytes.length - offset, charset); }
    }

    private String decodeStrict(byte[] bytes, Charset charset, int offset) throws CharacterCodingException {
        return charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes, offset, bytes.length - offset)).toString();
    }

    private boolean startsWith(byte[] bytes, int... prefix) {
        if (bytes.length < prefix.length) return false;
        for (int index = 0; index < prefix.length; index++) {
            if ((bytes[index] & 0xFF) != prefix[index]) return false;
        }
        return true;
    }

    private Charset detectUnmarkedUtf16(byte[] bytes) {
        int sampleLength = Math.min(bytes.length, 1024);
        if (sampleLength < 8) return null;
        int oddZeros = 0, evenZeros = 0, pairs = sampleLength / 2;
        for (int index = 0; index + 1 < sampleLength; index += 2) {
            if (bytes[index] == 0) evenZeros++;
            if (bytes[index + 1] == 0) oddZeros++;
        }
        if (oddZeros / (double) pairs > 0.3) return StandardCharsets.UTF_16LE;
        if (evenZeros / (double) pairs > 0.3) return StandardCharsets.UTF_16BE;
        return null;
    }
}
