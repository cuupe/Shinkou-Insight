import test from "node:test";
import assert from "node:assert/strict";
import { researchElapsed, researchStageIndex, researchSummary, isResearchActive, researchErrorHelp } from "../src/utils/researchRun.ts";

test("input cannot appear as an analysis result", () => {
  assert.equal(researchSummary({ status: "RUNNING", goal: "计划试点" }), "");
  assert.equal(researchSummary({ status: "COMPLETED", report: { executive_summary: "需要补充证据" } }), "需要补充证据");
});
test("refresh preserves elapsed time and terminal duration stops advancing", () => {
  const startedAt = "2026-09-28T00:00:00Z";
  const now = Date.parse(startedAt) + 65000;
  assert.equal(researchElapsed({ status: "RUNNING", startedAt }, now), "1 分 5 秒");
  assert.equal(researchElapsed({ status: "FAILED", startedAt, durationSeconds: 12 }, now + 60000), "12 秒");
  assert.equal(researchElapsed({ status: "PENDING" }, now), "等待开始");
});
test("failed stage comes from actual events; unopened stages remain pending", () => {
  assert.equal(researchStageIndex({ status: "FAILED", currentNode: "FAILED", events: [{ node: "PLAN", type: "node.failed" }] }), 0);
  assert.equal(researchStageIndex({ status: "PENDING" }), -1);
  assert.equal(researchStageIndex({ status: "COMPLETED" }), 4);
  assert.equal(isResearchActive({ status: "FAILED" }), false);
  assert.equal(isResearchActive({ status: "PAUSED" }), true);
});
test("timeout and network interruptions offer actionable recovery", () => {
  assert.match(researchErrorHelp("LLM request timed out"), /时限/);
  assert.match(researchErrorHelp("incomplete chunked read"), /连接中断/);
});
