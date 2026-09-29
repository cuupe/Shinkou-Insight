package com.cuupe.backend.modules.ai;

import com.cuupe.backend.common.exception.ApiException;
import com.cuupe.backend.modules.asset.entity.KnowledgeAsset;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.*;

class AiIndexingClientTest {
    private HttpServer server;
    private AiIndexingClient client;
    private final ObjectMapper json = new ObjectMapper();
    private final AtomicReference<Map> received = new AtomicReference<>();
    private int status = 200;
    private String response = "{\"chunkCount\":2}";
    private long delay;

    @BeforeEach void startServer() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal", exchange -> {
            received.set(json.readValue(exchange.getRequestBody().readAllBytes(), Map.class));
            try { Thread.sleep(delay); } catch (InterruptedException exception) { Thread.currentThread().interrupt(); }
            byte[] body = response.getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(status, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        client = new AiIndexingClient(json, "http://127.0.0.1:" + server.getAddress().getPort(), "test", "http://unused", 30);
    }

    @AfterEach void stopServer() { server.stop(0); }

    private KnowledgeAsset asset() {
        KnowledgeAsset asset = new KnowledgeAsset();
        asset.setId(9L); asset.setProjectId(8L); asset.setName("自定义显示标题");
        asset.setStorageKey("workspaces/7/projects/8/assets/checksum/original.docx");
        return asset;
    }

    @Test void slowIndexingSurvivesDefaultTenSecondReadLimitAndPreservesFilename() throws Exception {
        delay = 10500;
        client.index(asset(), 7L, 1L, Map.of(), null);
        assertEquals("original.docx", received.get().get("fileName"));
    }

    @Test void parserFailureIsReportedAndEmptyIndexIsNotSuccess() {
        status = 422; response = "{\"detail\":\"文件未解析出可索引的文本\"}";
        assertEquals("文件未解析出可索引的文本", assertThrows(IOException.class, () -> client.index(asset(), 7L, 1L, Map.of(), null)).getMessage());
        status = 200; response = "{\"chunkCount\":0}";
        assertTrue(assertThrows(IOException.class, () -> client.index(asset(), 7L, 1L, Map.of(), null)).getMessage().contains("未生成"));
    }

    @Test void unavailableKnowledgeServiceHasActionableApiError() {
        server.stop(0);
        assertTrue(assertThrows(ApiException.class, () -> client.knowledge("/internal/knowledge/search", Map.of())).getMessage().contains("Python"));
    }
}
