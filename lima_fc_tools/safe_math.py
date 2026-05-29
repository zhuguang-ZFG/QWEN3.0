"""Bounded AST math evaluation for Telegram function-calling tools."""

from __future__ import annotations

import ast
import math
import operator

MAX_EXPR_LEN = 200
MAX_DEPTH = 24
MAX_ABS_RESULT = 1e100

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_ALLOWED_NAMES = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
    "pow": pow,
}


def evaluate_math_expression(expression: str) -> float:
    expr = (expression or "").strip()
    if not expr:
        raise ValueError("empty expression")
    if len(expr) > MAX_EXPR_LEN:
        raise ValueError("expression too long")
    tree = ast.parse(expr, mode="eval")
    value = _eval_node(tree.body, depth=0)
    if not isinstance(value, (int, float)):
        raise ValueError("non-numeric result")
    if math.isinf(value) or math.isnan(value):
        raise ValueError("invalid numeric result")
    if abs(value) > MAX_ABS_RESULT:
        raise ValueError("result too large")
    return float(value)


def _eval_node(node: ast.AST, *, depth: int) -> float:
    if depth > MAX_DEPTH:
        raise ValueError("expression too deep")

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.Name):
        if node.id not in _ALLOWED_NAMES:
            raise ValueError("unsupported name")
        value = _ALLOWED_NAMES[node.id]
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError("unsupported name")

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return float(_UNARY_OPS[type(node.op)](_eval_node(node.operand, depth=depth + 1)))

    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left, depth=depth + 1)
        right = _eval_node(node.right, depth=depth + 1)
        if isinstance(node.op, ast.Pow) and (abs(right) > 64 or abs(left) > 1e6):
            raise ValueError("exponent too large")
        return float(_BIN_OPS[type(node.op)](left, right))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("unsupported call")
        fn = _ALLOWED_NAMES.get(node.func.id)
        if not callable(fn):
            raise ValueError("unsupported call")
        if node.keywords:
            raise ValueError("keyword arguments not allowed")
        if len(node.args) > 8:
            raise ValueError("too many arguments")
        args = [_eval_node(arg, depth=depth + 1) for arg in node.args]
        return float(fn(*args))

    raise ValueError("unsupported expression")
