from __future__ import annotations

from crypto_alpha_agent.agents.llm_contracts import HypothesisProposal


def test_blocks_mev_and_mempool_text_with_reason_code():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea("Detect MEV and mempool sandwiches on DEX routes")

    assert decision.approved is False
    assert decision.reason_codes == ["mev_or_mempool"]
    assert "mev" in decision.matched_terms
    assert "mempool" in decision.matched_terms


def test_blocks_premium_private_rpc_text_with_reason_code():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea({"thesis": "Use premium RPC and private RPC to scan faster"})

    assert decision.approved is False
    assert decision.reason_codes == ["premium_rpc_required"]
    assert "premium rpc" in decision.matched_terms
    assert "private rpc" in decision.matched_terms


def test_blocks_bridge_race_and_flash_loan_race():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        "Bridge race using flash loan liquidity to beat cross-chain arbitrageurs"
    )

    assert decision.approved is False
    assert decision.reason_codes == ["bridge_race", "flash_loan_race"]
    assert "bridge race" in decision.matched_terms
    assert "flash loan" in decision.matched_terms


def test_blocks_plural_bridge_races():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea("Run bridge races across chains")

    assert decision.approved is False
    assert decision.reason_codes == ["bridge_race"]
    assert "bridge races" in decision.matched_terms


def test_blocks_plural_flash_loans_used_for_races():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea("Use flash loans to race liquidations")

    assert decision.approved is False
    assert decision.reason_codes == ["flash_loan_race"]
    assert "flash loans" in decision.matched_terms


def test_blocks_sub_second_cex_dex_arbitrage():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        "Sub-second CEX-DEX arbitrage using low-latency order routing"
    )

    assert decision.approved is False
    assert decision.reason_codes == ["sub_second_arbitrage"]
    assert "sub-second arbitrage" in decision.matched_terms


def test_blocks_live_orders_and_wallet_key_references():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    proposal = HypothesisProposal(
        proposal_id="p-1",
        thesis="Research only",
        hypothesis="Investigate funding dislocations",
        assumptions=["public APIs are sufficient"],
        evidence=["historical data"],
        disconfirmation=["funding signal not persistent"],
        data_needed=["funding rates"],
        capital_required_usd=50.0,
    )

    decision = guard_generated_idea(
        {
            "proposal": proposal,
            "notes": "Would place live orders with wallet keys and a private key",
        }
    )

    assert decision.approved is False
    assert decision.reason_codes == ["live_trading_required", "wallet_key_required"]
    assert "live orders" in decision.matched_terms
    assert "wallet keys" in decision.matched_terms
    assert "private key" in decision.matched_terms


def test_blocks_joined_and_camelcase_unsafe_terms():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        "Use flashLoan liquidity with premiumRPC and privateRPC, "
        "walletKeys, liveOrders, and a bridgeRace"
    )

    assert decision.approved is False
    assert decision.reason_codes == [
        "premium_rpc_required",
        "bridge_race",
        "flash_loan_race",
        "live_trading_required",
        "wallet_key_required",
    ]
    assert "premium rpc" in decision.matched_terms
    assert "private rpc" in decision.matched_terms
    assert "bridge race" in decision.matched_terms
    assert "flash loan" in decision.matched_terms
    assert "live orders" in decision.matched_terms
    assert "wallet keys" in decision.matched_terms


def test_allows_explicit_negative_unsafe_metadata_flags():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        {
            "thesis": "Funding basis research using public APIs",
            "private_key_required": False,
            "premium_rpc_required": False,
            "live_orders_required": False,
        }
    )

    assert decision.approved is True
    assert decision.reason_codes == []
    assert decision.matched_terms == []


def test_blocks_high_capital_metadata_above_budget():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        {
            "thesis": "Historical basis research",
            "capital_required_usd": 1_000.0,
            "source": "public APIs",
        }
    )

    assert decision.approved is False
    assert decision.reason_codes == ["capital_above_budget"]
    assert decision.capital_required_usd == 1000.0
    assert decision.max_capital_usd == 300.0


def test_blocks_high_capital_text_phrase_above_budget():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea("Basis trade requires 10,000 USD to be practical")

    assert decision.approved is False
    assert decision.reason_codes == ["capital_above_budget"]
    assert decision.capital_required_usd == 10000.0
    assert "requires 10,000 USD" in decision.matched_terms


def test_allows_low_capital_text_phrase_within_budget():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea("Funding research requires 100 USD for sampling")

    assert decision.approved is True
    assert decision.reason_codes == []
    assert decision.capital_required_usd == 100.0


def test_allows_funding_basis_research_with_public_apis_and_low_capital():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        {
            "thesis": "Funding and basis research across exchanges using ordinary public APIs",
            "capital_required_usd": 250.0,
            "data_needed": ["funding rates", "basis history", "open interest"],
            "notes": "Backtest public historical data and report repeatable dislocations",
        }
    )

    assert decision.approved is True
    assert decision.reason_codes == []
    assert decision.matched_terms == []


def test_returns_stable_deduplicated_reason_codes_and_matched_terms():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        "MEV mempool sandwich with premium RPC and premium RPC plus MEV again"
    )

    assert decision.approved is False
    assert decision.reason_codes == ["mev_or_mempool", "premium_rpc_required"]
    assert decision.matched_terms == ["mev", "mempool", "sandwich", "premium rpc"]


def test_does_not_false_positive_on_safe_substrings():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

    decision = guard_generated_idea(
        "Somevenue administrative funding research with ordinary public APIs"
    )

    assert decision.approved is True
    assert decision.reason_codes == []
