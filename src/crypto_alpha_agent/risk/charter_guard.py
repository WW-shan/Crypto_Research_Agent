from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CharterRejectReason = Literal[
    "mev_or_mempool",
    "premium_rpc_required",
    "bridge_race",
    "flash_loan_race",
    "sub_second_arbitrage",
    "live_trading_required",
    "wallet_key_required",
    "capital_above_budget",
    "large_balance_sheet_required",
]

CAPITAL_METADATA_KEYS = {
    "capital_required_usd",
    "min_capital_usd",
    "required_capital_usd",
    "notional_usd",
}

_TOKEN_BOUNDARY_START = r"(?<![A-Za-z0-9])"
_TOKEN_BOUNDARY_END = r"(?![A-Za-z0-9])"
_TERM_SEPARATOR_PATTERN = r"[\s_-]+"


class CharterGuardDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    approved: bool
    reason_codes: list[CharterRejectReason] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    capital_required_usd: float | None = Field(default=None, ge=0)
    max_capital_usd: float = Field(ge=0)
    allowed_family: str | None = None


def guard_generated_idea(
    idea: Any, *, max_capital_usd: float = 300.0
) -> CharterGuardDecision:
    strings: list[str] = []
    capital_values: list[float] = []
    metadata_reasons: list[CharterRejectReason] = []
    _collect_idea_fields(
        idea,
        strings=strings,
        capital_values=capital_values,
        metadata_reasons=metadata_reasons,
    )

    reason_codes: list[CharterRejectReason] = []
    matched_terms: list[str] = []
    for text in strings:
        _scan_text(
            text,
            reason_codes=reason_codes,
            matched_terms=matched_terms,
            capital_values=capital_values,
            max_capital_usd=max_capital_usd,
        )

    for reason in metadata_reasons:
        _append_unique(reason_codes, reason)

    capital_required_usd = max(capital_values) if capital_values else None
    if capital_required_usd is not None and capital_required_usd > max_capital_usd:
        _append_unique(reason_codes, "capital_above_budget")

    allowed_family = _allowed_family(strings) if not reason_codes else None
    return CharterGuardDecision(
        approved=not reason_codes,
        reason_codes=reason_codes,
        matched_terms=matched_terms,
        capital_required_usd=capital_required_usd,
        max_capital_usd=max_capital_usd,
        allowed_family=allowed_family,
    )


def _collect_idea_fields(
    value: Any,
    *,
    strings: list[str],
    capital_values: list[float],
    metadata_reasons: list[CharterRejectReason],
    current_key: str | None = None,
) -> None:
    if isinstance(value, BaseModel):
        _collect_idea_fields(
            value.model_dump(mode="python"),
            strings=strings,
            capital_values=capital_values,
            metadata_reasons=metadata_reasons,
            current_key=current_key,
        )
        return

    if isinstance(value, str):
        strings.append(value)
        if _is_capital_key(current_key):
            capital = _coerce_capital(value)
            if capital is not None:
                capital_values.append(capital)
        return

    if isinstance(value, bool) or value is None:
        return

    if isinstance(value, int | float):
        if _is_capital_key(current_key):
            capital = _coerce_capital(value)
            if capital is not None:
                capital_values.append(capital)
        return

    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            strings.append(key_text)
            normalized_key = _normalize_key(key_text)
            if normalized_key == "speed_dependency" and str(item).strip().lower() == "high":
                _append_unique(metadata_reasons, "sub_second_arbitrage")
            if normalized_key == "rpc_dependency" and str(item).strip().lower() == "high":
                _append_unique(metadata_reasons, "premium_rpc_required")
            if normalized_key == "action_mode" and str(item).strip().lower() in {
                "live",
                "gated_live",
            }:
                _append_unique(metadata_reasons, "live_trading_required")
            _collect_idea_fields(
                item,
                strings=strings,
                capital_values=capital_values,
                metadata_reasons=metadata_reasons,
                current_key=key_text,
            )
        return

    if isinstance(value, Iterable):
        for item in value:
            _collect_idea_fields(
                item,
                strings=strings,
                capital_values=capital_values,
                metadata_reasons=metadata_reasons,
                current_key=current_key,
            )


def _scan_text(
    text: str,
    *,
    reason_codes: list[CharterRejectReason],
    matched_terms: list[str],
    capital_values: list[float],
    max_capital_usd: float,
) -> None:
    for reason, term, pattern in _TEXT_RULES:
        if pattern.search(text):
            _append_unique(reason_codes, reason)
            _append_unique(matched_terms, term)

    for match in _CAPITAL_PHRASE_PATTERN.finditer(text):
        amount = _parse_amount(match.group("amount"))
        if amount is not None:
            capital_values.append(amount)
            if amount > max_capital_usd:
                _append_unique(matched_terms, match.group(0).strip())
                _append_unique(reason_codes, "capital_above_budget")


def _allowed_family(strings: list[str]) -> str | None:
    text = " ".join(strings).lower()
    if any(term in text for term in ("funding", "basis", "open interest", "historical")):
        return "funding_basis_public_data"
    return None


def _term_pattern(term: str) -> re.Pattern[str]:
    parts = [part for part in re.split(r"[\s_-]+", term.lower()) if part]
    body = _TERM_SEPARATOR_PATTERN.join(re.escape(part) for part in parts)
    return re.compile(f"{_TOKEN_BOUNDARY_START}{body}{_TOKEN_BOUNDARY_END}", re.IGNORECASE)


def _regex_rule(reason: CharterRejectReason, term: str, body: str) -> tuple[
    CharterRejectReason, str, re.Pattern[str]
]:
    return (reason, term, re.compile(body, re.IGNORECASE))


def _term_rule(
    reason: CharterRejectReason, term: str
) -> tuple[CharterRejectReason, str, re.Pattern[str]]:
    return (reason, term, _term_pattern(term))


_TEXT_RULES = (
    _term_rule("mev_or_mempool", "mev"),
    _term_rule("mev_or_mempool", "mempool"),
    _term_rule("mev_or_mempool", "sandwich"),
    _term_rule("premium_rpc_required", "premium rpc"),
    _term_rule("premium_rpc_required", "private rpc"),
    _term_rule("bridge_race", "bridge race"),
    _term_rule("bridge_race", "bridge races"),
    _term_rule("flash_loan_race", "flash loan"),
    _term_rule("flash_loan_race", "flash loans"),
    _regex_rule(
        "sub_second_arbitrage",
        "sub-second arbitrage",
        rf"{_TOKEN_BOUNDARY_START}sub[\s_-]*second\b.*\barbitrage{_TOKEN_BOUNDARY_END}",
    ),
    _regex_rule(
        "sub_second_arbitrage",
        "cex-dex arbitrage",
        rf"{_TOKEN_BOUNDARY_START}cex[\s_-]*dex[\s_-]+arbitrage{_TOKEN_BOUNDARY_END}",
    ),
    _term_rule("live_trading_required", "live order"),
    _term_rule("live_trading_required", "live orders"),
    _term_rule("live_trading_required", "live execution"),
    _term_rule("live_trading_required", "order placement"),
    _term_rule("live_trading_required", "place order"),
    _term_rule("wallet_key_required", "private key"),
    _term_rule("wallet_key_required", "private keys"),
    _term_rule("wallet_key_required", "seed phrase"),
    _term_rule("wallet_key_required", "wallet key"),
    _term_rule("wallet_key_required", "wallet keys"),
    _term_rule("large_balance_sheet_required", "large balance sheet"),
    _term_rule("large_balance_sheet_required", "institutional balance sheet"),
)

_CAPITAL_PHRASE_PATTERN = re.compile(
    rf"{_TOKEN_BOUNDARY_START}"
    r"(?:requires?|need(?:s|ed)?|capital(?:\s+required)?(?:\s+of)?)\s+"
    r"(?P<amount>\$?\d[\d,]*(?:\.\d+)?)\s*(?:usd|usdt|dollars?)"
    rf"{_TOKEN_BOUNDARY_END}",
    re.IGNORECASE,
)


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _is_capital_key(key: str | None) -> bool:
    return key is not None and _normalize_key(key) in CAPITAL_METADATA_KEYS


def _coerce_capital(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        capital = float(value)
    elif isinstance(value, str):
        capital = _parse_amount(value)
        if capital is None:
            return None
    else:
        return None

    if not math.isfinite(capital) or capital < 0:
        return None
    return capital


def _parse_amount(value: str) -> float | None:
    match = re.search(r"\$?(?P<amount>\d[\d,]*(?:\.\d+)?)", value)
    if match is None:
        return None
    return float(match.group("amount").replace(",", ""))


def _append_unique[T](values: list[T], value: T) -> None:
    if value not in values:
        values.append(value)
