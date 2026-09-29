package com.cuupe.backend.modules.asset.service;

import com.cuupe.backend.modules.ai.AiIndexingClient;
import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import com.cuupe.backend.modules.asset.mapper.KnowledgeAssetMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import java.io.IOException;
import java.util.Map;
import static org.mockito.Mockito.*;

class AssetIndexingServiceTest {
    private final KnowledgeAssetMapper mapper = mock(KnowledgeAssetMapper.class);
    private final AiIndexingClient client = mock(AiIndexingClient.class);
    private final AssetIndexingService service = new AssetIndexingService(mapper, client);
    private final KnowledgeAsset asset = new KnowledgeAsset();

    AssetIndexingServiceTest() { asset.setId(9L); asset.setProjectId(8L); }

    @AfterEach void clearTransaction() {
        if (TransactionSynchronizationManager.isSynchronizationActive()) TransactionSynchronizationManager.clearSynchronization();
    }

    @Test void indexingStartsOnlyAfterCommit() throws Exception {
        TransactionSynchronizationManager.initSynchronization();
        service.schedule(asset, 7L, 1L, Map.of(), null);
        verifyNoInteractions(client, mapper);
        TransactionSynchronizationManager.getSynchronizations().forEach(TransactionSynchronization::afterCommit);
        verify(mapper, timeout(2000)).markIndexed(9L, 8L);
        verify(client).index(asset, 7L, 1L, Map.of(), null);
    }

    @Test void rollbackDoesNotDispatchIndexing() {
        TransactionSynchronizationManager.initSynchronization();
        service.schedule(asset, 7L, 1L, Map.of(), null);
        TransactionSynchronizationManager.getSynchronizations().forEach(sync -> sync.afterCompletion(TransactionSynchronization.STATUS_ROLLED_BACK));
        verifyNoInteractions(client, mapper);
    }

    @Test void failedIndexKeepsActionableReason() throws Exception {
        doThrow(new IOException("文件未解析出可索引的文本")).when(client).index(asset, 7L, 1L, Map.of(), null);
        service.schedule(asset, 7L, 1L, Map.of(), null);
        verify(mapper, timeout(2000)).markIndexFailed(9L, 8L, "文件未解析出可索引的文本");
        verify(mapper, never()).markIndexed(anyLong(), anyLong());
    }
}
