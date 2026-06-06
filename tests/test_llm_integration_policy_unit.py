from __future__ import annotations

from llm_integration_policy import _is_retryable_real_llm_failure


def test_empty_responses_output_is_retryable_real_llm_provider_failure() -> None:
    assert _is_retryable_real_llm_failure(
        "LLMProviderError: LLM provider response did not contain output text: "
        "status=completed output_len=0 output_tokens=5"
    )


def test_invalid_llm_schema_is_not_retryable_real_llm_provider_failure() -> None:
    assert not _is_retryable_real_llm_failure(
        "LLMRuntimeError: schema_validation_failed: response did not match schema"
    )
