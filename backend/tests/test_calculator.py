import pytest

from app.core.errors import ToolFailure
from app.tools.calculator import calculate


def test_basic_arithmetic():
    assert calculate("2 + 2") == 4
    assert calculate("10 / 4") == 2.5
    assert calculate("2 ** 8") == 256
    assert calculate("(3 + 4) * 2") == 14


def test_division_by_zero_raises_tool_failure():
    with pytest.raises(ToolFailure):
        calculate("1 / 0")


def test_disallows_arbitrary_code():
    for malicious in ["__import__('os').system('ls')", "open('/etc/passwd').read()", "[].__class__"]:
        with pytest.raises(ToolFailure):
            calculate(malicious)


def test_disallows_oversized_expression():
    with pytest.raises(ToolFailure):
        calculate("1+" * 500)


def test_disallows_huge_exponent():
    with pytest.raises(ToolFailure):
        calculate("2 ** 999999")
