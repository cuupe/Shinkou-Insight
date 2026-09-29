package com.cuupe.backend.modules.agent.service;

import com.cuupe.backend.modules.agent.entity.*;
import com.cuupe.backend.modules.agent.mapper.AgentMapper;
import com.cuupe.backend.modules.ai.AiIndexingClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import java.util.concurrent.CopyOnWriteArrayList;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AgentServiceProgressTest {
    private final AgentMapper mapper = mock(AgentMapper.class);
    private final AiIndexingClient ai = mock(AiIndexingClient.class);
    private final ObjectMapper json = new ObjectMapper();
    private final List<AgentRunEvent> events = new ArrayList<>();
    private final AgentRun run = new AgentRun();
    private final AgentMessage answer = new AgentMessage();
    private AgentService service;

    @BeforeEach
    void setup() {
        service = new AgentService(mapper, json, null, null, ai, null, null, null, null);
        run.setId(10L); run.setRunKey("run-1"); run.setThreadId(20L);
        run.setAssistantMessageId(30L); run.setStatus("RUNNING");
        answer.setId(30L); answer.setClientMessageId("answer-1"); answer.setRole("ASSISTANT");
        answer.setStatus("STREAMING"); answer.setContent("");
        when(mapper.findRun("run-1", 1L, 1L)).thenReturn(run);
        when(mapper.findMessageKey(30L)).thenReturn("answer-1");
        when(mapper.findEvents("run-1", null)).thenAnswer(invocation -> new ArrayList<>(events));
        when(mapper.hasProjectAccess(1L, 1L, 1L)).thenReturn(true);
        doAnswer(invocation -> {
            AgentRunEvent event = invocation.getArgument(0);
            event.setId((long) events.size() + 1);
            events.add(event);
            return 1;
        }).when(mapper).insertEvent(any());
        doAnswer(invocation -> {
            answer.setContent(invocation.getArgument(1));
            answer.setStatus(invocation.getArgument(2));
            return 1;
        }).when(mapper).updateMessage(eq(30L), anyString(), anyString());
        doAnswer(invocation -> { run.setStatus(invocation.getArgument(1)); return 1; })
                .when(mapper).updateRun(eq(10L), anyString(), nullable(String.class));
        AgentThread thread = new AgentThread(); thread.setId(20L); thread.setThreadKey("thread-1");
        when(mapper.findThreads(1L, 1L)).thenReturn(List.of(thread));
        when(mapper.findMessages(20L, 1L, 1L)).thenReturn(List.of(answer));
        when(mapper.findRunsByThread(20L)).thenReturn(List.of(run));
    }

    @Test
    void storedContextIsAnchoredToTheCurrentTurnAndExcludesFailedAnswers() {
        run.setUserMessageId(25L);
        AgentMessage earlier = new AgentMessage();
        earlier.setId(21L); earlier.setRole("USER"); earlier.setContent("x=300000, y=284756");
        AgentMessage good = new AgentMessage();
        good.setId(22L); good.setRole("ASSISTANT"); good.setStatus("COMPLETED"); good.setContent("已记住");
        AgentMessage failed = new AgentMessage();
        failed.setId(23L); failed.setRole("ASSISTANT"); failed.setStatus("FAILED"); failed.setContent("000000000");
        AgentMessage future = new AgentMessage();
        future.setId(27L); future.setRole("USER"); future.setContent("下一个任务");
        when(mapper.findContextMessages(20L, 1L, 1L, 25L)).thenReturn(List.of(earlier, good, failed, future));
        var history = service.storedContextMessages(run, 1L, 1L);
        assertEquals(2, history.size());
        assertEquals("x=300000, y=284756", history.getFirst().get("content"));
        assertEquals("assistant", history.getLast().get("role"));
        verify(mapper).findContextMessages(20L, 1L, 1L, 25L);
    }

    @Test
    void privateReasoningCallbacksAreNotPersisted() {
        callback("thinking.delta", Map.of("delta", "PRIVATE_REASONING"));
        assertTrue(events.isEmpty());
    }

    private void callback(String type, Map<String, Object> payload) {
        service.handleAiCallback("run-1", Map.of("projectId", 1L, "userId", 1L,
                "eventType", type, "payload", payload));
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> restoredAnswer() {
        return ((List<Map<String, Object>>) service.history(1L, 1L).getFirst().get("messages")).getFirst();
    }

    @Test
    void callbacksAndHistoryPreserveActualTasksThinkingWhitespaceAndElapsedTime() {
        callback("run.started", Map.of("startedAt", "2026-09-27T01:00:00Z"));
        callback("agent.started", Map.of("task", Map.of("id", "child-1", "parentId", "run-1:primary",
                "title", "资料检索", "objective", "数据库迁移证据", "status", "running")));
        callback("thinking.started", Map.of("startedAt", "2026-09-27T01:00:05Z"));
        callback("thinking.delta", Map.of("delta", "先检查证据"));
        callback("thinking.delta", Map.of("delta", "\n"));
        callback("thinking.completed", Map.of("finishedAt", "2026-09-27T01:00:12Z", "durationMs", 7000));
        callback("message.delta", Map.of("delta", "## 标题"));
        callback("message.delta", Map.of("delta", "\n\n"));
        callback("message.delta", Map.of("delta", "正文"));
        Map<String, Object> streaming = restoredAnswer();
        assertEquals("## 标题\n\n正文", streaming.get("content"));
        assertNull(streaming.get("thinking"));
        assertEquals(7000L, streaming.get("thinkingDurationMs"));
        assertEquals("2026-09-27T01:00:00Z", streaming.get("runStartedAt"));
        callback("agent.failed", Map.of("task", Map.of("id", "child-1", "status", "failed", "error", "检索不可用")));
        callback("run.completed", Map.of("report", "## 最终答案\n\n保留格式",
                "startedAt", "2026-09-27T01:00:00Z", "finishedAt", "2026-09-27T01:01:10Z", "durationMs", 70000,
                "multiAgent", Map.of("enabled", true, "fallback", true, "reason", "子任务检索失败")));
        Map<String, Object> restored = restoredAnswer();
        assertEquals("completed", restored.get("status"));
        assertEquals(70000, restored.get("runDurationMs"));
        assertEquals(String.valueOf(events.size()), restored.get("lastEventId"));
        assertTrue(String.valueOf(restored.get("agentTasks")).contains("检索不可用"));
        assertEquals("## 最终答案\n\n保留格式", restored.get("content"));
        assertEquals("message.replace", events.get(events.size() - 3).getEventType());
        assertTrue(events.stream().allMatch(event -> event.getPayload().contains("timestamp")));
        assertEquals(70000, service.history(1L, 1L).getFirst().get("runDurationMs"));
    }

    @Test
    void cancellationPreservesPartialAnswerAndTerminatesOutstandingTasks() throws Exception {
        callback("run.started", Map.of("startedAt", "2026-09-27T01:00:00Z"));
        callback("agent.started", Map.of("task", Map.of("id", "child-1", "status", "running")));
        callback("message.delta", Map.of("delta", "已经生成的答案"));
        service.cancel(1L, 1L, 1L, "run-1");
        verify(ai).cancelRun("run-1");
        Map<String, Object> restored = restoredAnswer();
        assertEquals("已经生成的答案\n\n已由你暂停本次运行。", restored.get("content"));
        assertEquals("CANCELLED", restored.get("runStatus"));
        assertTrue(String.valueOf(restored.get("agentTasks")).contains("cancelled"));
        assertNotNull(restored.get("runFinishedAt"));
        assertNotNull(restored.get("runDurationMs"));
        int count = events.size();
        callback("message.delta", Map.of("delta", "迟到的回调"));
        assertEquals(count, events.size());
    }

    @Test
    @SuppressWarnings("unchecked")
    void stepUpdatesKeepStartTimeAndDistinctAssignmentsAreNotOverwritten() {
        callback("node.started", Map.of("node", "INTERNAL_RESEARCHER", "title", "资料检索 · 1", "detail", "开始"));
        callback("node.started", Map.of("node", "INTERNAL_RESEARCHER", "title", "资料检索 · 2", "detail", "开始"));
        List<Map<String, Object>> before = (List<Map<String, Object>>) restoredAnswer().get("events");
        callback("node.completed", Map.of("node", "INTERNAL_RESEARCHER", "title", "资料检索 · 1", "detail", "返回结果"));
        callback("node.failed", Map.of("node", "INTERNAL_RESEARCHER", "title", "资料检索 · 2", "detail", "连接失败"));
        List<Map<String, Object>> after = (List<Map<String, Object>>) restoredAnswer().get("events");
        assertEquals(2, after.size());
        assertEquals(before.getFirst().get("startedAt"), after.getFirst().get("startedAt"));
        assertEquals("failed", after.getLast().get("status"));
        callback("tool.started", Map.of("tool", "search_knowledge", "callId", "call-1"));
        callback("tool.started", Map.of("tool", "search_knowledge", "callId", "call-2"));
        callback("tool.completed", Map.of("tool", "search_knowledge", "callId", "call-1"));
        callback("tool.failed", Map.of("tool", "search_knowledge", "callId", "call-2"));
        List<Map<String, Object>> withTools = (List<Map<String, Object>>) restoredAnswer().get("events");
        assertEquals(4, withTools.size());
        assertEquals("completed", withTools.get(2).get("status"));
        assertEquals("failed", withTools.get(3).get("status"));
    }

    @Test
    void replayKeepsSeparateAnswersAndFinishesInterruptedThinking() {
        Map<String, Object> first = new LinkedHashMap<>(Map.of("status", "streaming"));
        Map<String, Object> second = new LinkedHashMap<>(Map.of("status", "streaming"));
        AgentProgress.apply(first, "run.started", Map.of("startedAt", "2026-09-27T01:00:00Z"));
        AgentProgress.apply(first, "thinking.started", Map.of("startedAt", "2026-09-27T01:00:10Z"));
        AgentProgress.apply(second, "thinking.delta", Map.of("delta", "第二轮", "timestamp", "2026-09-27T02:00:00Z"));
        AgentProgress.apply(first, "run.failed", Map.of("timestamp", "2026-09-27T01:00:20Z"));
        assertEquals(20000L, first.get("runDurationMs"));
        assertEquals(10000L, first.get("thinkingDurationMs"));
        assertNull(second.get("thinking"));
        assertFalse(second.containsKey("runFinishedAt"));
    }

    @Test
    void failedRunsPreservePartialContentAndStopTheSidebarSteps() {
        callback("node.started", Map.of("node", "SYNTHESIS", "title", "生成回答"));
        callback("message.delta", Map.of("delta", "已生成部分"));
        callback("run.failed", Map.of("message", "连接中断", "durationMs", 15000));
        assertEquals("已生成部分\n\n运行失败：连接中断", restoredAnswer().get("content"));
        assertEquals("failed", restoredAnswer().get("status"));
        assertTrue(String.valueOf(service.history(1L, 1L).getFirst().get("events")).contains("status=failed"));
    }

    @Test
    void reconnectUsesTheHistoryCursor() {
        when(mapper.findEvents("run-1", 42L)).thenReturn(List.of());
        assertNotNull(service.subscribe(1L, 1L, 1L, "run-1", 42L));
        verify(mapper).findEvents("run-1", 42L);
    }

    @Test
    @SuppressWarnings("unchecked")
    void completionIsPublishedAndStreamClosedOnlyAfterPersistenceCommits() throws Exception {
        SseEmitter emitter = mock(SseEmitter.class);
        Map<String, CopyOnWriteArrayList<SseEmitter>> subscribers =
                (Map<String, CopyOnWriteArrayList<SseEmitter>>) ReflectionTestUtils.getField(service, "subscribers");
        subscribers.put("run-1", new CopyOnWriteArrayList<>(List.of(emitter)));
        TransactionSynchronizationManager.initSynchronization();
        TransactionSynchronizationManager.setActualTransactionActive(true);
        try {
            callback("run.completed", Map.of("report", "完成"));
            verifyNoInteractions(emitter);
            TransactionSynchronizationManager.getSynchronizations().forEach(sync -> sync.afterCommit());
            verify(emitter, times(3)).send(any(SseEmitter.SseEventBuilder.class));
            verify(emitter).complete();
        } finally {
            TransactionSynchronizationManager.clear();
        }
    }
}
