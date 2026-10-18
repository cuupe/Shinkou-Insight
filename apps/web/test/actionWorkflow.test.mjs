import test from "node:test";
import assert from "node:assert/strict";
import { actionRow, actionCommand, actionMetadataEditable, actionDue, actionStatusLabel, isActionVerified, actionDisplayStatus, actionBoardBucket } from "../src/utils/actionWorkflow.ts";
const base = { id: 1, title: "权限回归", ownerId: 1, acceptanceCriteria: "提供可核验的执行记录", status: "DRAFT", priority: "HIGH", canEdit: true, canManage: false };
test("task submission and acceptance are separate steps", () => {
    assert.deepEqual(actionCommand(base), { command: "start", label: "开始处理" });
    assert.deepEqual(actionCommand({ ...base, status: "IN_PROGRESS" }), { command: "submit", label: "提交验收" });
    assert.equal(actionCommand({ ...base, status: "PENDING_ACCEPTANCE" }), null);
    assert.deepEqual(actionCommand({ ...base, status: "PENDING_ACCEPTANCE", canAccept: true }), { command: "accept", label: "验收任务" });
    assert.equal(actionCommand({ ...base, status: "DONE" }), null);
    assert.deepEqual(actionCommand({ ...base, status: "DONE", canManage: true }), { command: "start", label: "重新打开" });
});
test("normalized UI rows retain source links, permissions and pending acceptance", () => {
    const row = actionRow({ ...base, status: "PENDING_ACCEPTANCE", sourceReportId: 8, sourceReviewRunId: 4, sourceExcerpt: "原始任务", canAccept: true });
    assert.equal(row.status, "pending-acceptance"); assert.equal(row.sourceReportId, 8); assert.equal(row.sourceExcerpt, "原始任务");
    assert.equal(actionCommand(row).command, "accept"); assert.equal(actionRow(row).priority, "高");
});
test("readers cannot change state and rejected work returns to execution", () => {
    assert.equal(actionCommand({ ...base, canEdit: false }), null);
    assert.deepEqual(actionCommand({ ...base, status: "REJECTED" }), { command: "start", label: "继续处理" });
});
test("only unaccepted legacy completion allows criteria repair before reopening", () => {
    assert.equal(actionMetadataEditable({ ...base, canManage: true, status: "DONE" }), true);
    assert.equal(actionMetadataEditable({ ...base, canManage: true, status: "DONE", acceptedAt: "2026-10-16" }), false);
    assert.equal(actionMetadataEditable({ ...base, canManage: true, status: "PENDING_ACCEPTANCE" }), false);
    assert.equal(actionMetadataEditable(base), false);
});
test("an overdue deadline excludes formally accepted tasks but retains legacy unverified completion", () => {
    assert.equal(actionDue({ ...base, dueAt: "2026-09-30" }, "2026-10-01").overdue, true);
    assert.equal(actionDue({ ...base, status: "DONE", dueAt: "2026-09-30", acceptedAt: "2026-10-01" }, "2026-10-02").overdue, false);
    const legacy = { ...base, status: "DONE", dueAt: "2026-09-30" };
    assert.equal(actionDue(legacy, "2026-10-01").overdue, true);
    assert.equal(isActionVerified(legacy), false); assert.equal(actionStatusLabel(legacy), "待补验收");
    assert.equal(actionDisplayStatus(legacy), "todo");
    assert.equal(actionDisplayStatus({ ...legacy, acceptedAt: "2026-10-01" }), "done");
});
test("today and absent deadlines have distinct labels without false overdue warnings", () => {
    assert.deepEqual(actionDue(base, "2026-10-18"), { label: "未设截止", full: "尚未设置截止日期", overdue: false, today: false });
    assert.equal(actionDue({ ...base, dueAt: "2026-10-18" }, "2026-10-18").label, "今天截止");
    assert.equal(actionDue({ ...base, dueAt: "2026-10-20" }, "2026-10-18").overdue, false);
});
test("the working board groups returned and legacy tasks under todo, while accepted work stays in history", () => {
    assert.equal(actionBoardBucket({ ...base, status: "REJECTED" }), "todo");
    assert.equal(actionBoardBucket({ ...base, status: "DONE" }), "todo");
    assert.equal(actionBoardBucket({ ...base, status: "DONE", acceptedAt: "2026-10-18" }), "done");
    assert.equal(actionBoardBucket({ ...base, status: "PENDING_ACCEPTANCE" }), "pending-acceptance");
});
test("an unassigned task asks its manager to assign an owner before attempting execution", () => {
    assert.deepEqual(actionCommand({ ...base, canManage: true, ownerId: null }), { command: "assign", label: "分派负责人" });
    assert.deepEqual(actionCommand({ ...base, canManage: true, ownerId: 1 }), { command: "start", label: "开始处理" });
});
test("a legacy task with missing acceptance criteria opens its requirements instead of sending an invalid transition", () => {
    assert.deepEqual(actionCommand({ ...base, status: "DONE", canManage: true, ownerId: 1, acceptanceCriteria: "" }), { command: "assign", label: "完善验收标准" });
});
