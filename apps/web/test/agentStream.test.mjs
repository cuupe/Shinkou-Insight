import assert from "node:assert/strict";
import test from "node:test";
import { watchAgentStream } from "../src/utils/agentStream.ts";

function source() {
  return { onmessage: null, onopen: null, onerror: null, closed: false, close() { this.closed = true; } };
}
const parse = message => JSON.parse(message.data);
const emit = (s, event) => s.onmessage({ data: JSON.stringify(event), lastEventId: event.eventId || "" });

test("a quiet open SSE stream recovers completion from the durable snapshot", async () => {
  const s = source(), events = [];
  await watchAgentStream({
    source: s, parse, onEvent: e => events.push(e), pollMs: 2,
    snapshot: async () => ({ runId: "r1", messageId: "m1", status: "COMPLETED", content: "2", events: [] })
  });
  assert.equal(s.closed, true);
  assert.deepEqual(events.map(e => e.type), ["message.replace", "message.completed", "run.completed"]);
  assert.equal(events[0].content, "2");
});

test("snapshot events deduplicate against SSE and retain the event cursor", async () => {
  const s = source(), events = [];
  const done = watchAgentStream({
    source: s, parse, onEvent: e => events.push(e), pollMs: 2, snapshot: async cursor => {
      assert.equal(cursor, "10000000000000000001");
      return {
        runId: "r", messageId: "m", status: "COMPLETED", events: [
          { type: "decision.updated", runId: "r", eventId: cursor },
          { type: "run.completed", runId: "r", eventId: "10000000000000000002" },
        ]
      };
    }
  });
  emit(s, { type: "decision.updated", runId: "r", eventId: "10000000000000000001" });
  await done;
  assert.equal(events.length, 2);
});

test("a missed failure event stops execution and preserves its concrete error", async () => {
  const s = source(), events = [];
  const done = watchAgentStream({
    source: s, parse, onEvent: e => events.push(e), pollMs: 2,
    snapshot: async () => ({ runId: "r", messageId: "m", status: "FAILED", events: [], error: { code: "TIMEOUT", stage: "decision", message: "模型响应超时" } })
  });
  await assert.rejects(done, /模型响应超时/);
  assert.equal(events.at(-1).error.code, "TIMEOUT");
  assert.equal(s.closed, true);
});

test("an event callback exception rejects instead of leaving the run running forever", async () => {
  const s = source();
  const done = watchAgentStream({
    source: s, parse, onEvent: () => { throw new Error("render error"); }, pollMs: 100,
    snapshot: async () => ({ runId: "r", messageId: "m", status: "RUNNING", events: [] })
  });
  emit(s, { type: "run.completed", runId: "r", eventId: "1" });
  await assert.rejects(done, /render error/);
  assert.equal(s.closed, true);
});

test("disconnect recovery never fabricates success when both transports fail", async () => {
  const s = source();
  const done = watchAgentStream({
    source: s, parse, onEvent: () => { }, pollMs: 5, reconnectMs: 20,
    snapshot: async () => { throw new Error("offline"); }
  });
  s.onerror({});
  await assert.rejects(done, /事件流与运行状态连接失败/);
  assert.equal(s.closed, true);
});
