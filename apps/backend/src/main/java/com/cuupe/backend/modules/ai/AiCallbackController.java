package com.cuupe.backend.modules.ai;

import com.cuupe.backend.modules.research.mapper.ResearchRunMapper;
import com.cuupe.backend.modules.agent.service.AgentService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.Set;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@RestController
@RequestMapping("/internal/ai")
@RequiredArgsConstructor
public class AiCallbackController {
    private final ResearchRunMapper researchRunMapper;
    private final AgentService agentService;

    @Value("${shinkou.ai.internal-api-key:local-dev-key}")
    private String internalApiKey;

    @PostMapping("/runs/{runId}/callback")
    public void callback(@PathVariable Long runId, @RequestHeader(value = "X-Internal-Api-Key", required = false) String apiKey, @RequestBody Map<String, Object> body) {
        verify(apiKey);
        Long projectId = longValue(body.get("projectId"));
        Long userId = longValue(body.get("userId"));
        String state = String.valueOf(body.getOrDefault("status", "RUNNING")).toUpperCase();
        if (projectId == null || userId == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "callback context missing");
        if (!Set.of("RUNNING", "COMPLETED", "FAILED", "CANCELLED").contains(state)) return;
        researchRunMapper.updateStatus(runId, projectId, userId, state);
    }

    @PostMapping("/agent-runs/{runKey}/callback")
    public void agentCallback(@PathVariable String runKey, @RequestHeader(value = "X-Internal-Api-Key", required = false) String apiKey, @RequestBody Map<String, Object> body) {
        verify(apiKey);
        agentService.handleAiCallback(runKey, body);
    }

    private void verify(String apiKey) {
        if (apiKey == null || internalApiKey == null
                || !MessageDigest.isEqual(
                internalApiKey.getBytes(StandardCharsets.UTF_8),
                apiKey.getBytes(StandardCharsets.UTF_8))) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "invalid internal api key");
        }
    }

    private Long longValue(Object value) {
        if (value == null) return null;
        try { return Long.valueOf(String.valueOf(value)); } catch (NumberFormatException ignored) { return null; }
    }
}
