import assert from "node:assert/strict";
import test from "node:test";
import MarkdownIt from "markdown-it";
import katex from "katex";
import texmath from "markdown-it-texmath";
import { normalizeAgentMarkdown } from "../src/utils/agentMarkdown.ts";

const markdown = new MarkdownIt({
  html: false,
  breaks: false,
  linkify: true,
}).use(texmath, {
  engine: katex,
  delimiters: ["dollars", "brackets", "beg_end"],
  katexOptions: { throwOnError: false, strict: "warn" },
});
const render = (source) => markdown.render(normalizeAgentMarkdown(source));

test("the calculation response keeps its title and section hierarchy without visible hashes", () => {
  const source =
    "# 计算结果\n\n## 直接结论\n\n1 + 1 的结果是 **2**。\n\n## 分点依据\n\n- **算术定义**：两个单位合并。\n\n## 限制与不确定性\n\n此结果基于标准实数或整数加法运算。\n\n## 可执行建议\n\n使用标准算术。";
  assert.equal(normalizeAgentMarkdown(source), source);
  const html = render(source);
  assert.match(html, /<h1>计算结果<\/h1>/);
  for (const section of [
    "直接结论",
    "分点依据",
    "限制与不确定性",
    "可执行建议",
  ]) {
    assert.ok(html.includes(`<h2>${section}</h2>`));
  }
  assert.doesNotMatch(html, /<h[1-6]>\s*#/);
  assert.match(html, /<strong>2<\/strong>/);
  assert.match(html, /<ul>/);
});

for (let level = 1; level <= 6; level++) {
  test(`level ${level} headings survive whitespace, adjacent blocks, and repeated normalization`, () => {
    const marker = "#".repeat(level);
    for (const gap of ["", " ", "\t", "&nbsp;", "&#32;"]) {
      const input = `${marker}${gap}标题\n\n${marker}${gap}下一节`;
      const normalized = normalizeAgentMarkdown(input);
      assert.equal(normalizeAgentMarkdown(normalized), normalized);
      assert.equal(
        render(input),
        `<h${level}>标题</h${level}>\n<h${level}>下一节</h${level}>\n`,
      );
    }
    assert.equal(
      render(`${marker} 标题 ${marker}`),
      `<h${level}>标题</h${level}>\n`,
    );
    assert.equal(render(`${marker}\n`), `<h${level}></h${level}>\n`);
    assert.equal(
      render(`> ${marker} 引用标题`),
      `<blockquote>\n<h${level}>引用标题</h${level}>\n</blockquote>\n`,
    );
  });
}

test("repairs provider headings without splitting an existing hash run", () => {
  for (let level = 2; level <= 6; level++) {
    assert.equal(
      render(`上一段。${"#".repeat(level)}下一节`),
      `<p>上一段。</p>\n<h${level}>下一节</h${level}>\n`,
    );
    assert.equal(
      render(`${"＃".repeat(level)}直接结论`),
      `<h${level}>直接结论</h${level}>\n`,
    );
  }
  assert.equal(render(String.raw`\#\# 直接结论`), "<h2>直接结论</h2>\n");
  assert.equal(
    render(String.raw`# 计算结果\n\n## 直接结论`),
    "<h1>计算结果</h1>\n<h2>直接结论</h2>\n",
  );
  assert.equal(
    render("##直接结论\r\n\r\n###分点依据\r\n"),
    "<h2>直接结论</h2>\n<h3>分点依据</h3>\n",
  );
});

test("hashes that are content stay content", () => {
  for (const source of [
    "####### 普通文本",
    "正文####### 普通文本",
    "# C# 示例",
    "## 使用 # 标签",
    "## 使用 ## 标签",
    "## C#",
    "###",
    "# ",
    "## ",
  ]) {
    assert.equal(render(source), markdown.render(source));
  }
});

test("inline code, fenced code, and incomplete streaming fences keep their literal content", () => {
  for (const source of [
    "`foo##bar`",
    "``正文 `## 标题` 字面量``",
    "路径：`C:\\new\\notes`",
    "```md\n## 直接结论\n正文##下一节\n```",
    "~~~md\n### 标题\n~~~",
    "````md\n```\n## 标题\n```\n````",
    "```md\n## 直接结论\n正文##下一节",
    "~~~md\n### 标题",
    "```md\r\n## 标题\r\n```\r\n\r\n## 正文",
  ]) {
    assert.equal(normalizeAgentMarkdown(source), source);
    assert.equal(render(source), markdown.render(source));
  }
});

test("every prefix of a streamed heading uses the same heading level as MarkdownIt", () => {
  for (let level = 1; level <= 6; level++) {
    const source = `# 计算结果\n\n${"#".repeat(level)} 直接结论\n\n1 + 1 = 2。`;
    for (let length = 1; length <= source.length; length++) {
      const prefix = source.slice(0, length);
      assert.equal(
        render(prefix),
        markdown.render(prefix),
        JSON.stringify(prefix),
      );
    }
  }
});

test("math, citations, links, lists, and tables survive heading normalization", () => {
  const source = String.raw`## 分点依据

- **数学公理**：$S(1) = 2$ [1]
- 行内公式：\(1 + 1 = 2\)
- 命令前缀：$1 \neq 2$，$\nabla f$

$$
1 + 1 = 2
$$

| 项目 | 值 |
| --- | --- |
| 结果 | 2 |

[参考](https://example.com/guide#addition)
`;
  assert.equal(render(source), markdown.render(source));
  assert.match(render(source), /class="katex"/);
  assert.match(render("## 公式\n\n`x = 2`"), /class="katex"/);
});
