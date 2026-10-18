import type { AgentRunSnapshot, AgentStreamEvent } from "../api/types";

/** One terminal state, whether delivered by SSE or the durable run snapshot. */
export function watchAgentStream({ source, parse, onEvent, snapshot, afterId = "", pollMs = 5000, reconnectMs = 15000 }: {
  source: Pick<EventSource, "onmessage" | "onopen" | "onerror" | "close">;
  parse: (message: MessageEvent<string>) => AgentStreamEvent | null;
  onEvent: (event: AgentStreamEvent) => void;
  snapshot: (afterId: string) => Promise<AgentRunSnapshot>;
  afterId?: string;
  pollMs?: number;
  reconnectMs?: number;
}) {
  return new Promise<void>((resolve, reject) => {
    let settled = false;
    let polling = false;
    let cursor = afterId;
    let snapshotAt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const seen = new Set<string>();
    const clearRetry = () => { if (retryTimer !== undefined) clearTimeout(retryTimer); retryTimer = undefined; };
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      clearInterval(pollTimer);
      clearRetry();
      source.close();
      if (error) reject(error); else resolve();
    };
    const ingest = (event: AgentStreamEvent, eventId?: string) => {
      if (settled) return;
      const id = String(event.eventId || eventId || "");
      if (id) {
        if (seen.has(id)) return;
        seen.add(id);
        try { if (!cursor || BigInt(id) > BigInt(cursor)) cursor = id; }
        catch { cursor = id; }
        if (seen.size > 4096) seen.delete(seen.values().next().value!);
      }
      try {
        onEvent(event);
        if (event.type === "run.failed") finish(new Error(event.message || "Agent 运行失败"));
        else if (event.type === "run.completed") finish();
      } catch (error) {
        // A rendering callback exception must also settle the pending promise.
        finish(error instanceof Error ? error : new Error("Agent 事件处理失败"));
      }
    };
    const poll = async () => {
      if (settled || polling) return;
      polling = true;
      try {
        const state = await snapshot(cursor);
        if (settled) return;
        snapshotAt = Date.now();
        for (const event of state.events) ingest(event);
        const status = state.status.toUpperCase();
        if (!settled && ["COMPLETED", "FAILED", "CANCELLED"].includes(status)) {
          if (state.content != null) ingest({ type: "message.replace", runId: state.runId, messageId: state.messageId, content: state.content });
          if (status !== "FAILED") ingest({ type: "message.completed", runId: state.runId, messageId: state.messageId });
          ingest({ ...state, type: status === "FAILED" ? "run.failed" : "run.completed", message: state.message || state.error?.message || "Agent 运行失败" } as AgentStreamEvent);
        }
      } catch { /* SSE remains primary; a transient snapshot failure is retryable. */ }
      finally { polling = false; }
    };
    const pollTimer = setInterval(() => { void poll(); }, pollMs);
    source.onmessage = message => {
      const event = parse(message);
      if (event) ingest(event, message.lastEventId);
    };
    source.onopen = clearRetry;
    source.onerror = () => {
      if (settled) return;
      void poll();
      if (retryTimer !== undefined) return;
      retryTimer = setTimeout(() => {
        retryTimer = undefined;
        if (Date.now() - snapshotAt > pollMs * 2) finish(new Error("Agent 事件流与运行状态连接失败"));
      }, reconnectMs);
    };
  });
}
