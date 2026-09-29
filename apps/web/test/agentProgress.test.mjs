import assert from "node:assert/strict";
import test from "node:test";
import {
  applyMessageProgress,
  currentMessageActivity,
  finishMessageProgress,
  messageElapsed,
} from "../src/utils/agentProgress.ts";

const start = "2026-09-27T01:00:00Z";
const at = (seconds) =>
  new Date(Date.parse(start) + seconds * 1000).toISOString();
const message = (id) => ({
  id,
  role: "assistant",
  content: "",
  createdAt: start,
  status: "streaming",
  runStartedAt: start,
});
const apply = (target, type, fields = {}, seconds = 0) =>
  applyMessageProgress(target, {
    type,
    runId: target.id + "-run",
    timestamp: at(seconds),
    ...fields,
  });

test("switching conversations cannot restart either answer's clock or mix its thinking", () => {
  const first = message("first");
  const second = message("second");
  second.runStartedAt = at(20);
  apply(first, "thinking.delta", { delta: "核对项目资料" }, 5);
  apply(second, "thinking.delta", { delta: "比较方案" }, 25);
  for (const target of [first, second, first]) {
    assert.equal(
      messageElapsed(target, Date.parse(at(40))),
      target === first ? 40000 : 20000,
    );
  }
  assert.equal(first.thinking, undefined);
  assert.equal(second.thinking, undefined);
  apply(first, "run.completed", { durationMs: 42000, finishedAt: at(42) }, 42);
  first.status = "completed";
  assert.equal(
    messageElapsed(JSON.parse(JSON.stringify(first)), Date.parse(at(100))),
    42000,
  );
});

test("independent child tasks retain real objectives, outcomes and failure status", () => {
  const target = message("tasks");
  for (const id of ["market", "risk"])
    apply(
      target,
      "agent.task.updated",
      {
        task: {
          id,
          parentId: "primary",
          agent: "researcher",
          title: id,
          objective: `${id} analysis`,
          status: "running",
          startedAt: at(1),
        },
      },
      1,
    );
  assert.equal(currentMessageActivity(target), "2 个子智能体正在执行");
  apply(
    target,
    "agent.task.updated",
    { task: { id: "risk", status: "failed", error: "检索失败" } },
    8,
  );
  assert.equal(target.agentTasks.length, 2);
  assert.equal(target.agentTasks[1].objective, "risk analysis");
  assert.equal(currentMessageActivity(target), "market");
  apply(
    target,
    "agent.task.updated",
    {
      task: { id: "market", status: "completed", summary: "未找到可引用证据" },
    },
    10,
  );
  apply(
    target,
    "run.completed",
    {
      multiAgent: {
        enabled: false,
        fallback: true,
        reason: "已回退到单智能体",
      },
    },
    15,
  );
  assert.equal(target.multiAgent.fallback, true);
  assert.equal(target.agentTasks[1].status, "failed");
});

test("progress details update without resetting the step start timestamp", () => {
  const target = message("steps");
  apply(
    target,
    "event.updated",
    {
      event: {
        id: "retrieve",
        kind: "search",
        title: "检索资料",
        detail: "开始",
        status: "running",
      },
    },
    2,
  );
  apply(
    target,
    "event.updated",
    {
      event: {
        id: "retrieve",
        kind: "search",
        title: "检索资料",
        detail: "读取原文",
        status: "running",
      },
    },
    8,
  );
  assert.equal(target.events[0].startedAt, at(2));
  assert.equal(target.events[0].detail, "读取原文");
  assert.equal(target.events.length, 1);
  finishMessageProgress(target, "cancelled", at(9));
  assert.equal(target.events[0].status, "cancelled");
  assert.equal(target.runDurationMs, 9000);
});

test("reasoning transitions to the answer and preserves measured time across reload", () => {
  const target = message("reasoning");
  apply(target, "thinking.started", { startedAt: at(3) }, 3);
  apply(target, "thinking.delta", { delta: "先核对" }, 4);
  apply(target, "thinking.delta", { delta: "，再回答。" }, 5);
  apply(
    target,
    "thinking.completed",
    { finishedAt: at(7), durationMs: 4000 },
    7,
  );
  apply(target, "message.delta", { delta: "## 结论" }, 7);
  assert.equal(target.answerStartedAt, at(7));
  assert.equal(target.thinkingSeconds, 4);
  assert.equal(JSON.parse(JSON.stringify(target)).thinking, undefined);
  apply(target, "thinking.started", { startedAt: at(8) }, 8);
  apply(
    target,
    "thinking.completed",
    { finishedAt: at(10), durationMs: 2000 },
    10,
  );
  assert.equal(target.thinkingDurationMs, 6000);
});

test("interrupted thinking freezes with the run and old answers do not acquire a live timer", () => {
  const target = message("cancel");
  apply(target, "thinking.started", { startedAt: at(2) }, 2);
  finishMessageProgress(target, "cancelled", at(9));
  assert.equal(target.thinkingDurationMs, 7000);
  assert.equal(messageElapsed(target, Date.parse(at(90))), 9000);
  assert.equal(
    messageElapsed(
      { ...message("old"), status: "completed" },
      Date.parse(at(90)),
    ),
    undefined,
  );
});
