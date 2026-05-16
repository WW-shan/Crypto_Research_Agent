from pathlib import Path


PROMPT_DIR = Path("src/crypto_alpha_agent/prompts")

PROMPTS = {
    "supervisor": PROMPT_DIR / "supervisor.md",
    "scanner": PROMPT_DIR / "scanner.md",
    "hypothesis_generator": PROMPT_DIR / "hypothesis_generator.md",
    "coder": PROMPT_DIR / "coder.md",
    "reflexion": PROMPT_DIR / "reflexion.md",
}

COMMON_TERMS = [
    "few hundred USD",
    "ordinary public APIs",
    "no premium RPC",
    "no MEV",
    "no sub-second arbitrage",
    "research-only",
    "JSON",
    "falsifiable",
    "disconfirmation",
    "assumptions",
    "evidence",
    "Reject speed-dependent ideas",
    "no live orders",
    "no wallet keys",
]

ROLE_TERMS = {
    "supervisor": ["route", "reject", "human approval"],
    "scanner": ["weak signal", "source", "liquidity"],
    "hypothesis_generator": ["hypothesis", "assumptions", "evidence"],
    "coder": ["backtest", "sandbox", ("no network", "restricted network")],
    "reflexion": ["failure", "lesson", "memory"],
}


def assert_contains_term(text: str, term: str | tuple[str, ...]) -> None:
    lower_text = text.lower()
    if isinstance(term, tuple):
        assert any(option.lower() in lower_text for option in term)
        return
    assert term.lower() in lower_text


def test_enumerates_all_agent_prompt_files() -> None:
    assert set(PROMPTS) == {
        "supervisor",
        "scanner",
        "hypothesis_generator",
        "coder",
        "reflexion",
    }


def test_prompts_include_shared_charter_constraints() -> None:
    for path in PROMPTS.values():
        text = path.read_text()

        for term in COMMON_TERMS:
            assert_contains_term(text, term)

        lower_text = text.lower()
        assert (
            "docs/project-charter.md" in lower_text
            or "project charter is governing" in lower_text
        )


def test_prompts_include_role_specific_contract_terms() -> None:
    for role, path in PROMPTS.items():
        text = path.read_text()

        for term in ROLE_TERMS[role]:
            assert_contains_term(text, term)


def test_coder_prompt_restricts_code_scope_to_allowed_values() -> None:
    text = PROMPTS["coder"].read_text()
    lower_text = text.lower()

    assert "deterministic analysis" not in lower_text
    assert '"code_scope": "backtest | transform | indicator"' in text


def test_prompts_force_assumptions_and_evidence_in_json_contracts() -> None:
    for path in PROMPTS.values():
        text = path.read_text()

        assert '"assumptions"' in text
        assert '"evidence"' in text


def test_coder_prompt_forbids_unrestricted_network_and_execution_adapters() -> None:
    text = PROMPTS["coder"].read_text()
    lower_text = text.lower()

    assert "unrestricted network" in lower_text
    assert "execution adapters" in lower_text
