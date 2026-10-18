import test from "node:test";
import assert from "node:assert/strict";
import { reportTextFields, reportUpdatePayload } from "../src/utils/reportContent.ts";

const content = "完整验收报告\n\n## 指标\n\n| 指标 | 结果 |\n|---|---|\n| 耗时降低 | 45% [E2] |\n\n## 成本\n\n139000元 [E11]\n\n## 行动项\n\n- A01权限撤销\n- A02故障演练\n- A03新增50条独立样本\n";

test("a short summary cannot hide the stored full report", () => {
  const fields = reportTextFields({summary:"八项达标，推广条件待关闭",content,markdownContent:"旧正文"});
  assert.equal(fields.summary,"八项达标，推广条件待关闭");
  assert.equal(fields.content,content);
  assert.match(fields.content,/139000元 \[E11\]/);
  assert.match(fields.content,/A03新增50条/);
});

test("legacy Markdown and summary-only reports remain readable", () => {
  assert.equal(reportTextFields({content:"  ",markdownContent:content,summary:"摘要"}).content,content);
  assert.equal(reportTextFields({lead:"摘要",summary:"摘要",recommendation:"补充验证"}).content,"摘要\n\n补充验证");
  assert.equal(reportTextFields({}).content,"");
});

test("editing metadata preserves the entire Markdown body byte for byte", () => {
  const fields=reportTextFields({lead:"导语",summary:"原摘要",content});
  const updated=reportUpdatePayload({...fields,title:"更新标题",summary:"更新摘要",recommendation:"更新建议"});
  assert.equal(updated.content,content);
  assert.equal(updated.summary,"更新摘要");
  assert.equal(updated.recommendation,"更新建议");
  assert.equal(updated.title,"更新标题");
});

test("editing the full body does not replace the independent summary", () => {
  const form={title:"验收报告",...reportTextFields({summary:"独立摘要",content})};
  const revised=content+"\n## 后续记录\n\n保留三项推广限制。\n";
  const updated=reportUpdatePayload({...form,content:revised});
  assert.equal(updated.content,revised);
  assert.equal(updated.summary,"独立摘要");
});
