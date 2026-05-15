from crypto_alpha_agent.agents.anomaly import AnomalyDetector
from crypto_alpha_agent.agents.scanner import MarketScanner, ScannerSignal


def test_scanner_returns_multiple_categories_from_injected_providers():
    scanner = MarketScanner(
        providers=[
            lambda: [
                ScannerSignal(
                    category="cex",
                    source="binance_order_book",
                    asset="ETH",
                    metric="spread_bps",
                    value=42.0,
                    evidence=["bid/ask spread widened to 42 bps"],
                    venue="binance",
                )
            ],
            lambda: [
                ScannerSignal(
                    category="dex",
                    source="curve_pool",
                    asset="ETH",
                    metric="liquidity_depth_usd",
                    value=1_800_000.0,
                    evidence=["2% depth fell while reward APR rose"],
                    protocol="curve",
                ),
                ScannerSignal(
                    category="chain",
                    source="ethereum_bridge_monitor",
                    asset="ETH",
                    metric="bridge_flow_usd",
                    value=9_500_000.0,
                    evidence=["bridge outflows exceeded trailing baseline"],
                    chain="ethereum",
                ),
                ScannerSignal(
                    category="social",
                    source="news_feed",
                    asset="ETH",
                    metric="mention_velocity",
                    value=6.0,
                    evidence=["headline cluster mentions unstaking delays"],
                    weak_signal=True,
                ),
            ],
        ]
    )

    signals = scanner.scan()

    assert {signal.category for signal in signals} == {"cex", "dex", "chain", "social"}
    assert {signal.source for signal in signals} == {
        "binance_order_book",
        "curve_pool",
        "ethereum_bridge_monitor",
        "news_feed",
    }


def test_output_preserves_raw_evidence_source_and_category_for_explainability():
    scanner = MarketScanner(
        providers=[
            lambda: [
                {
                    "category": "cex",
                    "source": "okx_funding",
                    "asset": "SOL",
                    "metric": "funding_rate",
                    "value": 0.004,
                    "evidence": ["funding moved 3.1 sigma above baseline"],
                    "raw": {"symbol": "SOL/USDT:USDT", "funding": 0.004},
                }
            ]
        ]
    )

    [signal] = scanner.scan()
    [anomaly] = AnomalyDetector().rank([signal])

    assert signal.category == "cex"
    assert signal.source == "okx_funding"
    assert signal.evidence == ["funding moved 3.1 sigma above baseline"]
    assert signal.raw == {"symbol": "SOL/USDT:USDT", "funding": 0.004}
    assert anomaly.signal.category == "cex"
    assert anomaly.signal.source == "okx_funding"
    assert anomaly.signal.evidence == ["funding moved 3.1 sigma above baseline"]


def test_anomaly_detector_ranks_persistent_statistical_structural_signal_above_social_noise():
    persistent_opportunity = ScannerSignal(
        category="dex",
        source="uniswap_v3_pool_monitor",
        asset="ARB",
        metric="liquidity_reward_dislocation",
        value=18.0,
        z_score=3.4,
        deviation=0.29,
        persistence_seconds=1_800,
        liquidity_usd=3_000_000,
        capital_required_usd=25_000,
        evidence=["reward APR changed", "liquidity depth stayed tradeable", "pool TVL diverged"],
        structural_break=True,
        protocol="uniswap",
    )
    social_noise = ScannerSignal(
        category="social",
        source="telegram_mentions",
        asset="ARB",
        metric="mention_velocity",
        value=22.0,
        z_score=5.0,
        deviation=0.75,
        persistence_seconds=60,
        liquidity_usd=0,
        evidence=["single viral post"],
        weak_signal=True,
    )

    ranked = AnomalyDetector().rank([social_noise, persistent_opportunity])

    assert ranked[0].signal is persistent_opportunity
    assert ranked[0].classification in {"statistical_outlier", "structural_discontinuity"}
    assert ranked[0].executable is True
    assert ranked[1].classification == "one_off_noise"
    assert ranked[1].executable is False


def test_impossible_to_trade_high_speed_high_capital_rpc_signal_is_mirage():
    mirage = ScannerSignal(
        category="chain",
        source="mempool_bridge_watcher",
        asset="USDC",
        metric="bridge_flow_latency_gap",
        value=1_000_000.0,
        z_score=9.0,
        deviation=0.9,
        persistence_seconds=5,
        liquidity_usd=50_000,
        capital_required_usd=20_000_000,
        speed_dependency="high",
        rpc_dependency="high",
        evidence=["gap visible for one block", "requires privileged RPC timing"],
        chain="ethereum",
    )
    executable = ScannerSignal(
        category="cex",
        source="borrow_rate_monitor",
        asset="BTC",
        metric="borrow_rate_deviation",
        value=0.08,
        z_score=2.7,
        deviation=0.18,
        persistence_seconds=3_600,
        liquidity_usd=10_000_000,
        capital_required_usd=50_000,
        evidence=["borrow rate persisted", "spot book depth is stable"],
        venue="coinbase",
    )

    ranked = AnomalyDetector().rank([mirage, executable])

    mirage_result = next(result for result in ranked if result.signal is mirage)
    executable_results = [result for result in ranked if result.executable]
    assert mirage_result.classification == "mirage"
    assert mirage_result.executable is False
    assert executable_results == [next(result for result in ranked if result.signal is executable)]


def test_capital_exceeds_liquidity_without_speed_rpc_constraints_is_not_executable():
    impossible_size = ScannerSignal(
        category="dex",
        source="thin_pool_monitor",
        asset="MKR",
        metric="pool_depth_dislocation",
        value=38.0,
        z_score=6.0,
        deviation=0.65,
        persistence_seconds=2_400,
        liquidity_usd=100_000,
        capital_required_usd=750_000,
        speed_dependency="low",
        rpc_dependency="none",
        evidence=["pool price diverged", "visible depth cannot support required size"],
        structural_break=True,
        protocol="curve",
    )
    executable = ScannerSignal(
        category="cex",
        source="funding_basis_monitor",
        asset="MKR",
        metric="funding_basis_deviation",
        value=12.0,
        z_score=3.0,
        deviation=0.22,
        persistence_seconds=1_800,
        liquidity_usd=5_000_000,
        capital_required_usd=50_000,
        evidence=["funding basis persisted", "order book supports target size"],
        venue="binance",
    )

    ranked = AnomalyDetector().rank([impossible_size, executable])

    impossible_result = next(result for result in ranked if result.signal is impossible_size)
    assert impossible_result.classification == "mirage"
    assert impossible_result.executable is False
    assert ranked.index(impossible_result) > ranked.index(next(result for result in ranked if result.signal is executable))
