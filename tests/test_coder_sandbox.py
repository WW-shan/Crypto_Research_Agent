from __future__ import annotations

import pytest


def test_safe_indicator_code_validates_and_executes():
    from crypto_alpha_agent.tools.sandbox import run_sandboxed_code, validate_python_code

    source = """
import math

def simple_momentum(prices):
    return prices[-1] - prices[0]

result = {
    "momentum": simple_momentum([100.0, 101.5, 103.0]),
    "root": math.sqrt(16),
}
"""

    validate_python_code(source)
    result = run_sandboxed_code(source)

    assert result.success is True
    assert result.error is None
    assert result.namespace["result"] == {"momentum": 3.0, "root": 4.0}


@pytest.mark.parametrize(
    "source",
    [
        "import os\nos.system('echo unsafe')",
        "import subprocess\nsubprocess.run(['echo', 'unsafe'])",
        "import socket\nsocket.socket()",
        "import requests\nrequests.get('https://example.com')",
        "from web3 import Web3\nWeb3().eth.send_transaction({})",
        "__import__('os').system('echo unsafe')",
        "eval('1 + 1')",
        "exec('result = 1')",
        "open('/tmp/unsafe.txt', 'w').write('unsafe')",
        "wallet.send_transaction({'to': '0x0'})",
    ],
)
def test_sandbox_rejects_dangerous_imports_and_calls(source):
    from crypto_alpha_agent.tools.sandbox import SandboxViolation, validate_python_code

    with pytest.raises(SandboxViolation):
        validate_python_code(source)


def test_coder_emits_only_allowed_strategy_code_kinds():
    from crypto_alpha_agent.agents.coder import StrategyCode, StrategyCoder

    coder = StrategyCoder()

    for kind in StrategyCode.allowed_kinds():
        strategy_code = coder.emit(kind)
        assert strategy_code.kind == kind
        assert strategy_code.source.strip()

    with pytest.raises(ValueError, match="Unsupported strategy code kind"):
        coder.emit("wallet_drain")


def test_generated_templates_contain_no_network_shell_or_wallet_calls():
    from crypto_alpha_agent.agents.coder import StrategyCode, StrategyCoder
    from crypto_alpha_agent.tools.sandbox import validate_python_code

    forbidden_fragments = (
        "os.",
        "subprocess",
        "socket",
        "requests",
        "web3",
        "send_transaction",
        "send_raw_transaction",
        "transfer(",
        "approve(",
        "eval(",
        "exec(",
        "open(",
        "__import__",
    )

    coder = StrategyCoder()
    for kind in StrategyCode.allowed_kinds():
        strategy_code = coder.emit(kind)
        lower_source = strategy_code.source.lower()
        assert not any(fragment in lower_source for fragment in forbidden_fragments)
        validate_python_code(strategy_code.source)


def test_generated_backtest_template_executes_with_toy_inputs():
    from crypto_alpha_agent.agents.coder import StrategyCoder
    from crypto_alpha_agent.tools.sandbox import run_sandboxed_code

    strategy_code = StrategyCoder().emit("backtest_script")
    result = run_sandboxed_code(strategy_code.source)

    assert result.success is True
    assert result.error is None
    assert "run_backtest" in result.namespace

    output = result.namespace["run_backtest"]([100.0, 103.0, 105.0], threshold=0.02)

    assert output["trades"] == [{"index": 1, "return": pytest.approx(0.03)}]
    assert output["net_return"] == pytest.approx(0.03)


def test_generated_data_transform_template_executes_with_toy_inputs():
    from crypto_alpha_agent.agents.coder import StrategyCoder
    from crypto_alpha_agent.tools.sandbox import run_sandboxed_code

    strategy_code = StrategyCoder().emit("data_transform")
    result = run_sandboxed_code(strategy_code.source)

    assert result.success is True
    assert result.error is None
    assert "normalize_prices" in result.namespace

    output = result.namespace["normalize_prices"](
        [
            {"timestamp": "2026-05-15T00:00:00Z", "price": "100.5"},
            {"timestamp": "2026-05-15T01:00:00Z", "price": 101},
        ]
    )

    assert output == [
        {"timestamp": "2026-05-15T00:00:00Z", "price": 100.5},
        {"timestamp": "2026-05-15T01:00:00Z", "price": 101.0},
    ]
