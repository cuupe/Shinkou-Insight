import test from "node:test";
import assert from "node:assert/strict";
import { researchElapsed, researchStageIndex, researchSummary, isResearchActive, researchErrorHelp, researchSections, researchVisibleList, researchMarkdown, researchOutcome } from "../src/utils/researchRun.ts";

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

test("semantic research nodes show their actual active stages", () => {
  assert.equal(researchStageIndex({ status: "RUNNING", currentNode: "DECISION" }), 1);
  assert.equal(researchStageIndex({ status: "RUNNING", currentNode: "SYNTHESIS" }), 2);
  assert.equal(researchStageIndex({ status: "RUNNING", currentNode: "REFLECTION" }), 3);
});

test("report headings and export keep content without duplicate gaps or empty sections", () => {
  const run = {
    status: "COMPLETED", report: {
      title: "试点评估", executive_summary: "成本已核实，周期待补充", sections: [
        { heading: "分析结果", content: "成本139000元。\n\n- 核实实际周期" },
      ], recommendations: [], limitations: ["核实实际周期"]
    }
  };
  assert.equal(researchSections(run)[0].title, "分析结果");
  assert.deepEqual(researchVisibleList(run, "limitations"), []);
  assert.equal(researchMarkdown(run).split("核实实际周期").length - 1, 1);
  assert.doesNotMatch(researchMarkdown(run), /## 建议|## 限制与待确认事项/);
  assert.equal(researchSections({ report: { sections: [{ content: "结果" }] } })[0].title, "分析结果");
});

test("partial and clarification outcomes do not imply completed acceptance", () => {
  assert.equal(researchOutcome({ report: { outcome: "PARTIAL" } }), "PARTIAL");
  assert.equal(researchOutcome({ report: { outcome: "NEEDS_INPUT" } }), "NEEDS_INPUT");
  assert.equal(researchOutcome({ reviewResult: { approved: false, issues: ["缺少依据"] } }), "PARTIAL");
  assert.equal(researchOutcome({ report: { outcome: "COMPLETE" } }), "COMPLETE");
});
