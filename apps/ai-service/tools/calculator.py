"""Bounded arithmetic only: no eval, imports, attributes or arbitrary Python."""

from __future__ import annotations

import ast
from fractions import Fraction
from typing import Any


def normalize_expression(expression: str) -> str:
    value = expression.strip().replace("−", "-").replace("×", "*").replace("÷", "/")
    value = value.replace("²", "**2").replace("³", "**3").replace("^", "**")
    # Identifiers are tokens, not sequences of single-letter variables.
    # The model must provide explicit multiplication, preserving names such
    # as first_floor or unit_price exactly as it bound them.
    return value


def calculate(
    expression: str, variables: dict[str, Any] | None = None
) -> dict[str, str]:
    value = normalize_expression(expression)
    if not value or len(value) > 2048:
        raise ValueError("表达式为空或过长")
    tree = ast.parse(value, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("表达式过于复杂")
    variables = variables or {}

    def bounded(number: Fraction) -> Fraction:
        if (
            number.numerator.bit_length() > 12000
            or number.denominator.bit_length() > 12000
        ):
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
                if (
                    max(left.numerator.bit_length(), left.denominator.bit_length())
                    * abs(right)
                    > 12000
                ):
                    raise ValueError("幂运算超出安全长度")
                result = left ** int(right)
            else:
                raise ValueError("不支持该运算")
            return bounded(result)
        raise ValueError("仅支持数字、变量、括号和加减乘除乘方")

    result = visit(tree.body)
    return {"expression": value, "result": str(result), "exact": "true"}


_CN_DIGITS = dict(zip("零一二三四五六七八九", range(10))) | {"两": 2, "〇": 0}


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
