package com.cuupe.backend.modules.asset.service;

import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import com.cuupe.backend.modules.asset.mapper.KnowledgeAssetMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class AssetIndexingService {
    private final KnowledgeAssetMapper assetMapper;
    private final AiIndexingClient aiClient;

    public void schedule(KnowledgeAsset asset, Long workspaceId, Long userId,
                         Map<String, Object> runtimeEmbedding, String chunkingConfig) {
        Runnable start = () -> Thread.startVirtualThread(() -> {
            try {
                aiClient.index(asset, workspaceId, userId, runtimeEmbedding, chunkingConfig);
                assetMapper.markIndexed(asset.getId(), asset.getProjectId());
            } catch (Exception exception) {
                assetMapper.markIndexFailed(asset.getId(), asset.getProjectId(), exception.getMessage());
            }
        });
        // Python uses another DB connection. It must see the asset and its
        // INDEXING state before it inserts chunks or reports completion.
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override public void afterCommit() { start.run(); }
            });
        } else {
            start.run();
        }
    }
}
