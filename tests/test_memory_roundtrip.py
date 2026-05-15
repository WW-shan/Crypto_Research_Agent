def _opportunity_payload(asset: str = "ETH") -> dict:
    return {
        "source": "dune",
        "venue": "binance",
        "asset": asset,
        "chain": "ethereum",
        "protocol": "aave",
        "edge_type": "funding_basis",
        "evidence": ["perp funding positive", "spot borrow stable"],
        "confidence": 0.82,
        "capital_required_usd": 250.0,
        "expected_net_pnl_usd": 18.0,
        "downside_usd": 30.0,
        "speed_dependency": "low",
        "rpc_dependency": "low",
    }


def test_memory_store_persists_structured_records_after_reopen(tmp_path):
    from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore

    store_path = tmp_path / "memory.jsonl"
    store = MemoryStore(store_path)
    record = MemoryRecord(
        record_id="basis-eth-repeatable",
        opportunity=_opportunity_payload(),
        hypothesis={
            "id": "hyp-eth-basis",
            "thesis": "ETH perp funding exceeds borrow and fee drag",
            "expected_edge": "funding capture",
        },
        score={
            "approved": True,
            "score": 88,
            "reasons": [],
            "capital_required_usd": 250.0,
            "current_capital_usd": 500.0,
            "expected_net_pnl_usd": 18.0,
            "max_downside_usd": 30.0,
            "repeatable": True,
            "speed_dependency": "low",
            "rpc_dependency": "low",
        },
        backtest_artifacts={
            "engine": "vectorbt",
            "metrics": {"net_return": 0.11, "max_drawdown": -0.03, "trade_count": 12},
        },
        paper_trade_outcome={
            "status": "filled",
            "realized_pnl_usd": 16.4,
            "notes": "fees matched estimate",
        },
        tags=["basis", "eth", "worked"],
    )

    saved = store.append(record)
    reopened = MemoryStore(store_path)
    loaded = reopened.get(saved.record_id)

    assert loaded == saved
    assert loaded is not None
    assert loaded.opportunity["asset"] == "ETH"
    assert loaded.hypothesis["thesis"] == "ETH perp funding exceeds borrow and fee drag"
    assert loaded.score["score"] == 88
    assert loaded.backtest_artifacts["metrics"]["trade_count"] == 12
    assert loaded.paper_trade_outcome["realized_pnl_usd"] == 16.4
    assert loaded.embedding


def test_retrieval_ranks_relevant_worked_and_illusion_cases_before_irrelevant(tmp_path):
    from crypto_alpha_agent.memory.retrieval import retrieve_similar
    from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore

    store = MemoryStore(tmp_path / "memory.jsonl")
    worked = store.append(
        MemoryRecord(
            record_id="eth-basis-worked",
            opportunity=_opportunity_payload("ETH"),
            hypothesis={"thesis": "ETH funding basis capture is repeatable during stable borrow"},
            score={"approved": True, "score": 91, "reasons": []},
            backtest_artifacts={"net_return": 0.09, "win_rate": 0.67},
            paper_trade_outcome={"status": "closed", "realized_pnl_usd": 12.2},
            tags=["eth", "funding", "basis", "worked"],
        )
    )
    illusion = store.append(
        MemoryRecord(
            record_id="eth-basis-illusion",
            opportunity=_opportunity_payload("ETH"),
            hypothesis={"thesis": "ETH funding basis looked profitable before borrow costs"},
            score={"approved": False, "score": 30, "reasons": ["net_pnl_below_minimum"]},
            rejected_reasons=["net_pnl_below_minimum", "borrow_cost_underestimated"],
            backtest_artifacts={"net_return": -0.02, "win_rate": 0.42},
            paper_trade_outcome={"status": "rejected", "realized_pnl_usd": 0.0},
            tags=["eth", "funding", "basis", "illusion"],
        )
    )
    irrelevant = store.append(
        MemoryRecord(
            record_id="sol-airdrop",
            opportunity={
                **_opportunity_payload("SOL"),
                "chain": "solana",
                "protocol": "jupiter",
                "edge_type": "airdrop_farming",
            },
            hypothesis={"thesis": "SOL wallet activity may qualify for incentive distribution"},
            score={"approved": False, "score": 45, "reasons": ["opportunity_not_repeatable"]},
            rejected_reasons=["opportunity_not_repeatable"],
            tags=["sol", "airdrop"],
        )
    )

    reopened = MemoryStore(store.path)
    results = retrieve_similar(reopened, "ETH funding basis with borrow cost illusion", top_k=3)

    assert {result.record.record_id for result in results[:2]} == {
        worked.record_id,
        illusion.record_id,
    }
    assert results[0].score > results[2].score
    assert results[1].score > results[2].score
    assert results[2].record.record_id == irrelevant.record_id

    failed_results = retrieve_similar(
        reopened,
        "ETH funding basis failed due to borrow cost",
        top_k=2,
        filters={"has_rejected_reasons": True},
    )

    assert failed_results[0].record.record_id == illusion.record_id
    assert all(result.record.rejected_reasons for result in failed_results)
