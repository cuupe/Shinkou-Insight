package com.cuupe.backend.modules.research.service;

import com.cuupe.backend.modules.research.mapper.ResearchRunMapper;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;
import org.mockito.ArgumentCaptor;

class ResearchRunProgressServiceTest {
    private final ResearchRunMapper mapper = mock(ResearchRunMapper.class);
    private final ResearchRunProgressService service = new ResearchRunProgressService(mapper);

    @Test void ordinaryEventsCannotRestartTheRunOrResetItsProgress() {
        for (String type : List.of("agent.started", "agent.completed", "node.completed", "run.queued")) {
            service.accept(1L, 2L, 3L, Map.of("eventType", type, "payload", Map.of()));
        }
        verifyNoInteractions(mapper);
        service.accept(1L, 2L, 3L, Map.of("eventType", "run.progress", "payload", Map.of("progress", 35, "currentStep", "检索资料")));
        verify(mapper).updateRuntime(1L, 2L, 3L, "RUNNING", 35, "检索资料", null, null);
    }

    @Test void timeoutReasonAndElapsedTimeSurviveCallbacks() {
        service.accept(1L, 2L, 3L, Map.of("eventType", "run.failed", "payload", Map.of("message", "目标拆解失败：模型超时", "durationMs", 65000)));
        verify(mapper).updateRuntime(1L, 2L, 3L, "FAILED", null, "分析失败", "目标拆解失败：模型超时", 65);
    }

    @Test void completionSavesOneDraftAndDuplicateCompletionDoesNotPublishAgain() {
        when(mapper.updateRuntime(eq(1L), eq(2L), eq(3L), eq("COMPLETED"), isNull(), anyString(), isNull(), isNull())).thenReturn(1, 0);
        Map<String, Object> body = Map.of("status", "COMPLETED", "report", Map.of("title", "试点评估", "executive_summary", "需要补充证据", "evidence_ids", List.of("E1"), "recommendations", List.of("先试点")));
        service.accept(1L, 2L, 3L, body);
        service.accept(1L, 2L, 3L, body);
        verify(mapper, times(1)).insertReport(eq(1L), eq(2L), eq(3L), eq("试点评估"), eq("需要补充证据"), eq("- 先试点"), contains("需要补充证据"), eq(1));
    }

    @Test void clarificationIsNotSavedAsAnEmptyReportDraft() {
        when(mapper.updateRuntime(eq(1L), eq(2L), eq(3L), eq("COMPLETED"), isNull(), anyString(), isNull(), isNull())).thenReturn(1);
        service.accept(1L,2L,3L,Map.of("status","COMPLETED","report",Map.of("outcome","NEEDS_INPUT","title","请补充资料")));
        verify(mapper).updateRuntime(1L,2L,3L,"COMPLETED",null,"等待补充资料",null,null);
        verify(mapper,never()).insertReport(anyLong(),anyLong(),anyLong(),anyString(),anyString(),anyString(),anyString(),anyInt());
    }

    @Test void partialReportKeepsKnownResultsAndDoesNotRepeatInlineLimitationsOrBlankHeadings() {
        when(mapper.updateRuntime(eq(1L),eq(2L),eq(3L),eq("COMPLETED"),isNull(),anyString(),isNull(),isNull())).thenReturn(1);
        service.accept(1L,2L,3L,Map.of("status","COMPLETED","report",Map.of(
            "outcome","PARTIAL","title","试点评估","executive_summary","成本已核对，周期待核实", "recommendations",List.of(),
            "sections",List.of(Map.of("heading","","content","总成本139000元。[E1]\n\n仍需核实周期")),
            "limitations",List.of("仍需核实周期"),"evidence_ids",List.of("E1"))));
        ArgumentCaptor<String> content=ArgumentCaptor.forClass(String.class);
        verify(mapper).insertReport(eq(1L),eq(2L),eq(3L),eq("试点评估"),anyString(),eq(""),content.capture(),eq(1));
        assertTrue(content.getValue().contains("139000"));
        assertTrue(content.getValue().contains("## 分析结果"));
        assertEquals(1,content.getValue().split("仍需核实周期",-1).length-1);
        assertFalse(content.getValue().contains("## 建议"));
        verify(mapper).updateRuntime(1L,2L,3L,"COMPLETED",null,"已形成部分结果",null,null);
    }
}
