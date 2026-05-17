from datetime import UTC, datetime

from crypto_alpha_agent.data.defillama import DefiLlamaResearchClient
from crypto_alpha_agent.data.dexscreener import DexScreenerClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        return FakeResponse(self.payload)


def test_dexscreener_pair_normalizes_liquidity_and_volume():
    payload = {
        "pairs": [
            {
                "chainId": "base",
                "dexId": "uniswap",
                "pairAddress": "0xabc",
                "baseToken": {"symbol": "ABC"},
                "quoteToken": {"symbol": "USDC"},
                "priceUsd": "1.23",
                "liquidity": {"usd": 120000},
                "volume": {"h24": 45000},
            }
        ]
    }
    client = DexScreenerClient(
        session=FakeSession(payload),
        now=lambda: datetime(2026, 5, 16, tzinfo=UTC),
    )

    pairs = client.search_pairs("ABC")

    assert pairs[0].chain == "base"
    assert pairs[0].liquidity_usd == 120000
    assert pairs[0].suitability.latency_dependency == "medium"
    assert pairs[0].suitability.execution_role == "research_only"
    assert pairs[0].suitability.unsuitable_reasons == []


def test_dexscreener_low_liquidity_pair_is_research_only():
    payload = {
        "pairs": [
            {
                "chainId": "base",
                "dexId": "uniswap",
                "pairAddress": "0xlow",
                "baseToken": {"symbol": "LOW"},
                "quoteToken": {"symbol": "USDC"},
                "priceUsd": "0.04",
                "liquidity": {"usd": "9999.99"},
                "volume": {"h24": "1250"},
            }
        ]
    }
    client = DexScreenerClient(
        session=FakeSession(payload),
        now=lambda: datetime(2026, 5, 16, tzinfo=UTC),
    )

    pairs = client.search_pairs("LOW")

    assert pairs[0].liquidity_usd == 9999.99
    assert pairs[0].suitability.execution_role == "research_only"
    assert "liquidity_too_low" in pairs[0].suitability.unsuitable_reasons


def test_dexscreener_pairs_by_token_addresses_calls_tokens_endpoint():
    payload = [
        {
            "chainId": "base",
            "dexId": "uniswap",
            "pairAddress": "0xpair",
            "baseToken": {"symbol": "ONE"},
            "quoteToken": {"symbol": "TWO"},
            "priceUsd": "2.5",
            "liquidity": {"usd": 25000},
            "volume": {"h24": 5000},
        }
    ]
    session = FakeSession(payload)
    client = DexScreenerClient(
        session=session,
        now=lambda: datetime(2026, 5, 16, tzinfo=UTC),
    )

    pairs = client.pairs_by_token_addresses("base", ["0x1", "0x2"])

    assert session.urls == ["https://api.dexscreener.com/tokens/v1/base/0x1,0x2"]
    assert pairs[0].base_token == "ONE"
    assert pairs[0].quote_token == "TWO"
    assert pairs[0].price_usd == 2.5


def test_defillama_yields_filter_low_tvl_pools_as_research_only():
    payload = {
        "data": [
            {"chain": "Base", "project": "aave", "symbol": "USDC", "tvlUsd": 5000, "apy": 7.2},
            {
                "chain": "Ethereum",
                "project": "aave",
                "symbol": "USDC",
                "tvlUsd": 5000000,
                "apy": 4.1,
            },
        ]
    }
    client = DefiLlamaResearchClient(
        session=FakeSession(payload),
        now=lambda: datetime(2026, 5, 16, tzinfo=UTC),
    )

    pools = client.yield_pools(min_tvl_usd=10000)

    assert [pool.chain for pool in pools] == ["Ethereum"]
    assert pools[0].suitability.rpc_dependency == "none"


def test_defillama_yields_use_yields_llama_base_url_by_default():
    session = FakeSession({"data": []})
    client = DefiLlamaResearchClient(session=session)

    client.yield_pools()

    assert session.urls == ["https://yields.llama.fi/pools"]
