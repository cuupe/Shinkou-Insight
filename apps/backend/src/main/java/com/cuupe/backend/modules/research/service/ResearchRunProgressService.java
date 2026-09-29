package com.cuupe.backend.modules.research.service;

import com.cuupe.backend.modules.research.mapper.ResearchRunMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class ResearchRunProgressService {
    private final ResearchRunMapper mapper;

    @Transactional
    public void accept(Long runId, Long projectId, Long userId, Map<String, Object> body) {
        String type = text(body.get("eventType"));
        Map<?, ?> payload = body.get("payload") instanceof Map<?, ?> value ? value : body;
        String status = switch (type) {
            case "run.started", "run.progress" -> "RUNNING";
            case "run.completed" -> "COMPLETED";
            case "run.failed" -> "FAILED";
            case "run.cancelled" -> "CANCELLED";
            case "plan.updated" -> Boolean.TRUE.equals(payload.get("paused")) ? "PAUSED" : "RUNNING";
            case "" -> text(body.get("status")).toUpperCase(java.util.Locale.ROOT);
            default -> "";
        };
        if (!List.of("RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED").contains(status)) return;
        Integer progress = payload.get("progress") instanceof Number number ? Math.clamp(number.intValue(), 0, 100) : null;
        String step = switch (status) {
            case "COMPLETED" -> "分析完成";
            case "FAILED" -> "分析失败";
            case "CANCELLED" -> "已取消";
            case "PAUSED" -> "已请求暂停";
            default -> payload.get("currentStep") == null ? null : text(payload.get("currentStep"));
        };
        Object rawError = payload.get("errorMessage") != null ? payload.get("errorMessage") : payload.get("message");
        String error = "FAILED".equals(status) ? limit(text(rawError).isBlank() ? "分析执行失败，请检查模型连接后重试。" : text(rawError), 1000) : null;
        Integer duration = payload.get("durationMs") instanceof Number number ? Math.max(0, number.intValue() / 1000) : null;
        int changed = mapper.updateRuntime(runId, projectId, userId, status, progress, step, error, duration);
        if (changed > 0 && "COMPLETED".equals(status) && payload.get("report") instanceof Map<?, ?> report) {
            String summary = text(report.get("executive_summary"));
            String recommendations = lines(report.get("recommendations"));
            StringBuilder content = new StringBuilder(summary);
            if (report.get("sections") instanceof List<?> sections) {
                for (Object item : sections) if (item instanceof Map<?, ?> section) {
                    content.append("\n\n## ").append(text(section.get("title"))).append("\n\n").append(text(section.get("content")));
                }
            }
            content.append("\n\n## 建议\n\n").append(recommendations);
            content.append("\n\n## 限制与待确认事项\n\n").append(lines(report.get("limitations")));
            int citations = report.get("evidence_ids") instanceof List<?> ids ? ids.size() : 0;
            mapper.insertReport(runId, projectId, userId, limit(text(report.get("title")), 255), summary, recommendations, content.toString(), citations);
        }
    }

    private static String text(Object value) { return value == null ? "" : String.valueOf(value); }
    private static String limit(String value, int max) { return value.substring(0, Math.min(value.length(), max)); }
    private static String lines(Object value) {
        return value instanceof List<?> list ? String.join("\n", list.stream().map(item -> "- " + text(item)).toList()) : text(value);
    }
}
