package com.cuupe.backend.modules.asset.mapper;

import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import java.util.List;
import java.util.Map;

@Mapper
public interface KnowledgeAssetMapper {
    List<KnowledgeAsset> findByProject(@Param("projectId") Long projectId, @Param("userId") Long userId);
    KnowledgeAsset findById(@Param("id") Long id, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int insert(KnowledgeAsset asset);
    int markDeleted(@Param("id") Long id, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int resetIndex(@Param("id") Long id, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int markIndexing(@Param("id") Long id, @Param("projectId") Long projectId);
    int markIndexed(@Param("id") Long id, @Param("projectId") Long projectId);
    int markIndexFailed(@Param("id") Long id, @Param("projectId") Long projectId, @Param("message") String message);
    List<Map<String, Object>> findChunks(@Param("assetId") Long assetId, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int deleteChunks(@Param("assetId") Long assetId);
    int insertChunk(@Param("assetId") Long assetId, @Param("chunkIndex") Integer chunkIndex, @Param("content") String content);
}
