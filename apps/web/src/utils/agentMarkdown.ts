function isLikelyInlineMath(value: string) {
  const expression = value.replace(/\s+/g, " ").trim();
  if (!expression || expression.length > 160 || !/[A-Za-z]/.test(expression)) {
    return false;
  }

  // Models often wrap short formulas in inline code instead of `$...$`.
  // Convert only recognizable math-shaped spans so paths, commands, and
  // ordinary code labels keep their code formatting.
  if (/^[A-Za-z]$/.test(expression)) return true;
  if (
    /^(?:sin|cos|tan|cot|sec|csc|log|ln|exp|sqrt|max|min|abs)\s*\(/i.test(
      expression,
    )
  ) {
    return true;
  }
  if (
    /\\(?:frac|sqrt|sum|int|cdot|times|sin|cos|tan|log|ln|alpha|beta|pi)\b/.test(
      expression,
    )
  ) {
    return true;
  }

  const mathCharacters = /^[A-Za-z0-9\s\\{}()[\]+\-*/=.,·×÷≤≥<>−^_]+$/;
  const hasEquationSignal = /[=^_]/.test(expression);
  const hasArithmeticSignal =
    /[+\-*/]/.test(expression) &&
    (/\d/.test(expression) || /\s[+\-*/]\s/.test(expression));
  return (
    (hasEquationSignal || hasArithmeticSignal) &&
    mathCharacters.test(expression)
  );
}

function normalizeInlineMathExpression(value: string) {
  return value
    .trim()
    .replace(
      /(?<!\\)\b(sin|cos|tan|cot|sec|csc|log|ln|exp|sqrt|max|min|abs)\b/gi,
      "\\$1",
    );
}

function protectInlineCode(value: string, protect: (value: string) => string) {
  return value.replace(
    /(?<![\\`])(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)/g,
    (full, delimiter: string, code: string) => {
      if (
        delimiter === "`" &&
        !code.includes("\n") &&
        isLikelyInlineMath(code)
      ) {
        return `$${normalizeInlineMathExpression(code)}$`;
      }
      return protect(full);
    },
  );
}

function protectFencedCode(value: string, protect: (value: string) => string) {
  const opening = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)(?:\r?\n|$)/gm;
  let result = "";
  let cursor = 0;
  let match: RegExpExecArray | null;
  while ((match = opening.exec(value))) {
    const marker = match[1]!;
    // Backtick fence info strings cannot contain backticks.
    if (marker[0] === "`" && match[2]!.includes("`")) continue;
    const closing = new RegExp(
      `^ {0,3}${marker[0]}{${marker.length},}[ \\t]*(?=\\r?$)`,
      "gm",
    );
    closing.lastIndex = opening.lastIndex;
    const end = closing.exec(value);
    // An unclosed fence is still code while the response is streaming.
    const endIndex = end ? end.index + end[0].length : value.length;
    result +=
      value.slice(cursor, match.index) +
      protect(value.slice(match.index, endIndex));
    cursor = endIndex;
    opening.lastIndex = endIndex;
    if (!end) break;
  }
  return result + value.slice(cursor);
}

function normalizeHeadings(value: string) {
  return value
    .split("\n")
    .map((line) => {
      // Read the entire marker run before deciding its level. A regex such as
      // (#{1,6})(?=\S) backtracks on "## Title" and produces "# # Title".
      const heading = line.match(/^([ \t]*)([#＃]+)([^\n]*)$/);
      if (heading) {
        const indent = heading[1]!;
        const marker = heading[2]!;
        const title = heading[3]!;
        if (marker.length > 6) return line;
        const spacing = title && !/^\s/.test(title) ? " " : "";
        return `${indent.length <= 3 ? indent : ""}${"#".repeat(marker.length)}${spacing}${title}`;
      }
      // Leave headings inside standard quote/list containers to MarkdownIt.
      if (/^[ \t]*(?:>|[-+*][ \t]|\d+[.)][ \t])/.test(line)) return line;
      // Recover only headings glued to preceding prose; never start matching
      // inside a hash run or reinterpret closing hashes in an existing heading.
      return line
        .replace(/([^\s#＃])([ \t]*#{2,6})(?!#)(?=[ \t]*[^\s#])/g, "$1\n$2 ")
        .replace(
          /([^\s#＃])([ \t]*#)(?=[ \t]*[一二三四五六七八九十百]+、)/g,
          "$1\n$2 ",
        );
    })
    .join("\n");
}

function normalizeMarkdownEntities(value: string) {
  // Providers sometimes serialize ordinary spaces as HTML entities. Decode
  // the common space forms before structural Markdown cleanup runs.
  return value
    .replace(/(?:&#x20;|&#xA0;|&#32;|&#160;|&nbsp;)/gi, " ")
    .replace(/\u00a0/g, " ");
}

export function normalizeAgentMarkdown(value: string) {
  const codeBlocks: string[] = [];
  const protectCode = (block: string) => {
    const index = codeBlocks.push(block) - 1;
    return `\u0000SHINKOU_CODE_${index}\u0000`;
  };
  const protectedValue = protectInlineCode(
    protectFencedCode(value, protectCode),
    protectCode,
  );
  const mathBlocks: string[] = [];
  // Protect math before decoding provider line breaks: commands such as
  // \neq and \nabla contain a literal backslash followed by n.
  const protectedMarkdown = protectedValue.replace(
    /(\$\$[\s\S]*?\$\$|\$(?!\$)[^\n$]+?\$(?!\$)|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\})/g,
    (block) => {
      const index = mathBlocks.push(block) - 1;
      return `\u0000SHINKOU_MATH_${index}\u0000`;
    },
  );
  const source = normalizeMarkdownEntities(
    protectedMarkdown
      // Some providers return JSON-style line breaks instead of real newlines.
      .replace(/\\r\\n/g, "\n")
      .replace(/\\n/g, "\n")
      // A stray backslash before a real newline is an escaping artifact, not content.
      .replace(/\\(?=\r?\n)/g, "")
      // Recover Markdown markers escaped by the model (\\#, \\*, \\**, \\[, …).
      .replace(/\\([#>*_`~\-\[\]+=])/g, "$1"),
  );
  const normalized = normalizeHeadings(source)
    // Models sometimes glue a list item to the previous sentence or heading,
    // for example "...一元一次方程的求解- 体现：...".
    .replace(/([^\n])\s*-\s+(?=[\u4e00-\u9fff])/g, "$1\n- ")
    .replace(/([^\n])\s*\*\s+(?=[\u4e00-\u9fff])/g, "$1\n* ")
    // Recover list markers and common Chinese report section headings.
    .replace(/(^|\n)([ \t]*)([-+])(?=\S)/g, "$1$2$3 ")
    .replace(/(^|\n)([ \t]*)\*(?=[^\s*])/g, "$1$2* ")
    .replace(/(^|\n)([ \t]*)(\d+[.)])(?=\S)/g, "$1$2$3 ")
    .replace(/(^|\n)([ \t]*)([一二三四五六七八九十]+、)(?=\S)/g, "$1$2## $3 ");
  return normalized
    .replace(/^题目所需知识点解析(?=\S)/, "# 题目所需知识点解析\n\n")
    .replace(/(^|\n)(##\s+[^\n]{2,80}?知识点)(?=[^：:\n])/g, "$1$2\n\n")
    .replace(
      /\u0000SHINKOU_MATH_(\d+)\u0000/g,
      (_match, index) => mathBlocks[Number(index)] || "",
    )
    .replace(
      /\u0000SHINKOU_CODE_(\d+)\u0000/g,
      (_match, index) => codeBlocks[Number(index)] || "",
    );
}
