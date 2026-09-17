"""
Calculator tool — safe arithmetic evaluation.

Uses Python's `ast` module to parse the expression into a syntax tree and
only walks a strict allowlist of node types. There is NO call to eval(),
exec(), or compile() of arbitrary code, so this cannot be used to execute
shell commands, imports, attribute access, or anything beyond arithmetic.
"""
import ast
import operator
from typing import Union

from app.core.errors import ToolFailure

Number = Union[int, float]

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 12


def _eval_node(node: ast.AST) -> Number:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ToolFailure("calculator", detail=f"unsupported constant: {node.value!r}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise ToolFailure("calculator", detail=f"operator not allowed: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Pow and abs(right) > MAX_EXPONENT:
            raise ToolFailure("calculator", detail="exponent too large")
        try:
            return _ALLOWED_BINOPS[op_type](left, right)
        except ZeroDivisionError as exc:
            raise ToolFailure("calculator", detail="division by zero") from exc

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise ToolFailure("calculator", detail=f"operator not allowed: {op_type.__name__}")
        return _ALLOWED_UNARYOPS[op_type](_eval_node(node.operand))

    raise ToolFailure("calculator", detail=f"unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> Number:
    """Evaluate a plain arithmetic expression safely. Raises ToolFailure on anything unsafe/invalid."""
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        raise ToolFailure("calculator", detail="expression missing or too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolFailure("calculator", detail=f"invalid expression syntax: {exc}") from exc
    return _eval_node(tree.body)
