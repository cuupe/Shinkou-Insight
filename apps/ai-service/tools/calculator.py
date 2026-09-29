"""Bounded arithmetic only: no eval, imports, attributes or arbitrary Python."""
from __future__ import annotations

import ast
import re
from fractions import Fraction
from typing import Any


def normalize_expression(expression: str) -> str:
    value = expression.strip().replace("−", "-").replace("×", "*").replace("÷", "/")
    value = value.replace("²", "**2").replace("³", "**3").replace("^", "**")
    value = re.sub(r"(?<=\d)(?=[a-zA-Z(])|(?<=[a-zA-Z)])(?=[a-zA-Z(])", "*", value)
    return value


def calculate(expression: str, variables: dict[str, Any] | None = None) -> dict[str, str]:
    value = normalize_expression(expression)
    if not value or len(value) > 2048:
        raise ValueError("表达式为空或过长")
    tree = ast.parse(value, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("表达式过于复杂")
    variables = variables or {}

    def bounded(number: Fraction) -> Fraction:
        if number.numerator.bit_length() > 12000 or number.denominator.bit_length() > 12000:
            raise ValueError("计算结果超出安全长度")
        return number

    def visit(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return bounded(Fraction(ast.get_source_segment(value, node)))
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"缺少变量 {node.id}，不能默认设为 0")
            raw = str(variables[node.id])
            if len(raw) > 2048:
                raise ValueError("变量数值过长")
            return bounded(Fraction(raw))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            number = visit(node.operand)
            return -number if isinstance(node.op, ast.USub) else number
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Pow):
                if right.denominator != 1 or abs(right) > 1000:
                    raise ValueError("仅支持绝对值不超过 1000 的整数指数")
                if max(left.numerator.bit_length(), left.denominator.bit_length()) * abs(right) > 12000:
                    raise ValueError("幂运算超出安全长度")
                result = left ** int(right)
            else:
                raise ValueError("不支持该运算")
            return bounded(result)
        raise ValueError("仅支持数字、变量、括号和加减乘除乘方")

    result = visit(tree.body)
    return {"expression": value, "result": str(result), "exact": "true"}


_CN_DIGITS = dict(zip("零一二三四五六七八九", range(10))) | {"两": 2, "〇": 0}
_NUMBER = r"(?:[-+]?\d[\d,]*(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
_PAIR = re.compile(rf"({_NUMBER})\s*(加|减|乘以?|除以?|[+*×÷−-])\s*({_NUMBER})")


def chinese_number(text: str) -> int | str:
    if text.lstrip("+-")[0].isdigit():
        return text.replace(",", "")
    total = section = digit = 0
    for char in text:
        if char in _CN_DIGITS:
            digit = _CN_DIGITS[char]
        elif char in "十百千":
            section += (digit or 1) * {"十": 10, "百": 100, "千": 1000}[char]
            digit = 0
        elif char == "万":
            total += (section + digit) * 10000
            section = digit = 0
        elif char == "亿":
            total = (total + section + digit) * 100000000
            section = digit = 0
    return total + section + digit


def expression_in(text: str) -> str | None:
    """Extract only an explicit arithmetic span, never numbers from prose."""
    spans = re.findall(r"[a-zA-Z\d(][a-zA-Z\d\s.,()+*/^²³×÷−-]*", text)
    spans = [span.strip(" .,\n") for span in spans if re.search(r"[+*/^²³×÷−-]", span)]
    for span in sorted(spans, key=len, reverse=True):
        if re.search(r"[a-zA-Z]{3,}|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", span):
            continue
        try:
            tree = ast.parse(normalize_expression(span), mode="eval")
            if all(isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name,
                                     ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd))
                   for node in ast.walk(tree)):
                return span
        except (ValueError, SyntaxError):
            pass
    pair = _PAIR.search(text)
    if pair:
        left, op, right = pair.groups()
        operator = {"加": "+", "减": "-", "乘": "*", "乘以": "*", "除": "/", "除以": "/"}.get(op, op)
        return f"{chinese_number(left)}{operator}{chinese_number(right)}"
    return None


def conversation_facts(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Preserve explicit user values and provenance; assistant guesses are excluded."""
    facts: dict[str, Any] = {"variables": {}}
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        text = str(message.get("content", ""))
        pair = _PAIR.search(text)
        if pair:
            facts["operands"] = [str(chinese_number(pair[1])), str(chinese_number(pair[3]))]
            facts["operandsTurn"] = index
        for name, raw in re.findall(rf"(?<![a-zA-Z])([a-zA-Z])\s*(?:=|等于|为)\s*({_NUMBER})", text):
            facts["variables"][name] = str(chinese_number(raw))
        if facts.get("operands") and re.search(r"(?:以上|上面|这两个|最开始|刚才|两个数字)", text) and re.search(r"(?<![a-zA-Z])x\s*(?:和|与|、|,|，|及)\s*y(?![a-zA-Z])", text, re.I):
            facts["variables"].update(zip(("x", "y"), facts["operands"]))
        expression = expression_in(text)
        if expression:
            facts["expression"] = expression
    return facts


def requested_calculation(goal: str, facts: dict[str, Any]) -> str | None:
    # Questions about code, dates or explanatory formulas should stay with the model.
    if any(word in goal for word in ("代码", "正则", "日期", "证明", "推导", "公式是什么", "解释", "为什么")):
        return None
    expression = expression_in(goal)
    if expression:
        remainder = goal.replace(expression, "").strip(" \n?？=。")
        if not remainder or any(word in goal for word in ("计算", "算一下", "等于", "多少", "求值", "表达式", "calculate", "evaluate")):
            return expression
    if re.fullmatch(r"(?:那|再|现在)?\s*(?:相减|相加|相乘|相除)(?:呢|是多少)?[？?。！!\s]*", goal) and facts.get("operands"):
        operator = next(op for word, op in (("减", "-"), ("加", "+"), ("乘", "*"), ("除", "/")) if word in goal)
        return operator.join(facts["operands"])
    return None
