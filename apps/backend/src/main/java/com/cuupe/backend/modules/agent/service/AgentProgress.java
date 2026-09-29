package com.cuupe.backend.modules.agent.service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Rebuild one answer's execution state from the same events sent over SSE. */
final class AgentProgress {
    private AgentProgress() {}

    @SuppressWarnings("unchecked")
    static void apply(Map<String, Object> message, String type, Map<String, Object> event) {
        Object timestamp = event.get("timestamp");
        switch (type) {
            case "run.started" -> copy(event, message, "startedAt", "runStartedAt");
            case "event.updated" -> snapshot(message, "events", event.get("event"));
            case "agent.task.updated" -> snapshot(message, "agentTasks", event.get("task"));
            case "thinking.started" -> {
                copy(event, message, "startedAt", "thinkingStartedAt");
                message.remove("thinkingFinishedAt");
            }
            case "thinking.delta" -> {
                // Old stored events contribute timing only, never private text.
                if (!message.containsKey("thinkingStartedAt") && timestamp != null) message.put("thinkingStartedAt", timestamp);
            }
            case "thinking.completed" -> {
                finishThinking(message, event.getOrDefault("finishedAt", timestamp), event.get("durationMs"));
            }
            case "message.delta", "message.replace" -> {
                Object content = event.getOrDefault("message.delta".equals(type) ? "delta" : "content", "");
                if (!String.valueOf(content).isEmpty()) {
                    if (timestamp != null) message.putIfAbsent("answerStartedAt", timestamp);
                    finishThinking(message, timestamp, null);
                }
                if ("streaming".equals(message.get("status"))) {
                    message.put("content", "message.replace".equals(type)
                            ? event.getOrDefault("content", "")
                            : String.valueOf(message.getOrDefault("content", "")) + event.getOrDefault("delta", ""));
                }
            }
            case "run.completed", "run.failed" -> {
                copy(event, message, "startedAt", "runStartedAt");
                copy(event, message, "finishedAt", "runFinishedAt");
                if (!message.containsKey("runFinishedAt") && timestamp != null) message.put("runFinishedAt", timestamp);
                copy(event, message, "durationMs", "runDurationMs");
                if (event.get("durationMs") == null) {
                    Long duration = elapsed(message.get("runStartedAt"), message.get("runFinishedAt"));
                    if (duration != null) message.put("runDurationMs", duration);
                }
                finishThinking(message, message.get("runFinishedAt"), null);
                copy(event, message, "multiAgent", "multiAgent");
                String status = "run.failed".equals(type) ? "failed" : "completed";
                message.put("status", status);
                message.put("runStatus", event.getOrDefault("status", status));
                // A cancelled/failed parent cannot leave apparently running children.
                for (String key : List.of("agentTasks", "events")) {
                    for (Map<String, Object> item : (List<Map<String, Object>>) message.getOrDefault(key, List.of())) {
                        if (List.of("running", "pending").contains(String.valueOf(item.get("status")))) {
                            item.put("status", "failed".equals(status) ? "failed" : "cancelled");
                            if (timestamp != null) item.put("completedAt", timestamp);
                        }
                    }
                }
            }
            default -> { }
        }
    }

    static void copy(Map<String, Object> source, Map<String, Object> target, String from, String to) {
        if (source.get(from) != null) target.put(to, source.get(from));
    }

    private static long number(Object value) {
        return value instanceof Number number ? Math.max(0, number.longValue()) : 0;
    }

    private static Long elapsed(Object start, Object end) {
        try {
            return Math.max(0, java.time.Duration.between(java.time.Instant.parse(String.valueOf(start)),
                    java.time.Instant.parse(String.valueOf(end))).toMillis());
        } catch (RuntimeException ignored) { return null; }
    }

    private static void finishThinking(Map<String, Object> message, Object end, Object duration) {
        if (end == null || !message.containsKey("thinkingStartedAt") || message.containsKey("thinkingFinishedAt")) return;
        message.put("thinkingFinishedAt", end);
        long total = number(message.get("thinkingDurationMs")) + number(duration != null ? duration : elapsed(message.get("thinkingStartedAt"), end));
        message.put("thinkingDurationMs", total);
        message.put("thinkingSeconds", total / 1000);
    }

    @SuppressWarnings("unchecked")
    private static void snapshot(Map<String, Object> message, String key, Object raw) {
        if (!(raw instanceof Map<?, ?> value) || value.get("id") == null) return;
        List<Map<String, Object>> items = (List<Map<String, Object>>) message.computeIfAbsent(key, ignored -> new ArrayList<>());
        Map<String, Object> existing = items.stream().filter(item -> value.get("id").equals(item.get("id"))).findFirst().orElse(null);
        if (existing == null) {
            existing = new LinkedHashMap<>();
            items.add(existing);
        }
        for (Map.Entry<?, ?> entry : value.entrySet()) existing.put(String.valueOf(entry.getKey()), entry.getValue());
    }
}
