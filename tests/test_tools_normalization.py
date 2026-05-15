from __future__ import annotations


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(self.payload)

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(self.payload)


def test_cex_snapshot_normalization():
    from crypto_alpha_agent.tools.cex import normalize_cex_snapshot

    raw = {"binance": {"BTC/USDT": {"bid": 65000, "ask": 65010}}}
    snap = normalize_cex_snapshot(raw)

    assert snap.best_bid == 65000
    assert snap.best_ask == 65010


def test_cex_snapshot_preserves_market_context_and_raw_evidence():
    from crypto_alpha_agent.tools.cex import normalize_cex_snapshot

    raw = {"binance": {"ETH/USDT": {"bid": 3200.5, "ask": 3201.25}}}
    snap = normalize_cex_snapshot(raw)

    assert snap.source == "cex"
    assert snap.venue == "binance"
    assert snap.symbol == "ETH/USDT"
    assert snap.asset == "ETH"
    assert snap.raw == raw


def test_dune_query_result_normalization():
    from crypto_alpha_agent.tools.dune import normalize_dune_query_result

    raw = {"result": {"rows": [{"asset": "BTC", "funding": "0.012"}]}}
    result = normalize_dune_query_result(raw, query_id=123)

    assert result.source == "dune"
    assert result.query_id == 123
    assert result.rows == [{"asset": "BTC", "funding": "0.012"}]
    assert result.raw == raw


def test_thegraph_query_result_normalization():
    from crypto_alpha_agent.tools.thegraph import normalize_thegraph_query_result

    raw = {"data": {"markets": [{"id": "weth-usdc", "liquidity": "1000"}]}}
    result = normalize_thegraph_query_result(raw, subgraph_url="https://example.test/subgraphs/name/demo")

    assert result.source == "thegraph"
    assert result.subgraph_url == "https://example.test/subgraphs/name/demo"
    assert result.data == raw["data"]
    assert result.raw == raw


def test_defillama_protocol_snapshot_normalization():
    from crypto_alpha_agent.tools.defillama import normalize_defillama_protocol_snapshot

    raw = {
        "name": "Aave",
        "slug": "aave",
        "chainTvls": {"Ethereum": {"tvl": 1_000_000}, "Arbitrum": {"tvl": 250_000}},
    }
    snapshot = normalize_defillama_protocol_snapshot(raw)

    assert snapshot.source == "defillama"
    assert snapshot.protocol == "Aave"
    assert snapshot.slug == "aave"
    assert snapshot.chain_tvls == {"Ethereum": 1_000_000.0, "Arbitrum": 250_000.0}
    assert snapshot.raw == raw


def test_thin_clients_accept_injected_sessions():
    from crypto_alpha_agent.tools.defillama import DefiLlamaClient
    from crypto_alpha_agent.tools.dune import DuneClient
    from crypto_alpha_agent.tools.thegraph import TheGraphClient

    dune_session = FakeSession({"result": {"rows": [{"asset": "SOL"}]}})
    dune = DuneClient(api_key="test-key", session=dune_session)
    dune_result = dune.execute_query(42)

    assert dune_result.rows == [{"asset": "SOL"}]
    assert dune_session.calls[0][0] == "GET"
    assert dune_session.calls[0][2]["headers"]["x-dune-api-key"] == "test-key"

    graph_session = FakeSession({"data": {"pools": []}})
    graph = TheGraphClient(session=graph_session)
    graph_result = graph.query("https://example.test/subgraph", "{ pools { id } }")

    assert graph_result.data == {"pools": []}
    assert graph_session.calls[0][0] == "POST"

    llama_session = FakeSession({"name": "Uniswap", "slug": "uniswap", "chainTvls": {"Ethereum": {"tvl": 5}}})
    llama = DefiLlamaClient(session=llama_session)
    llama_result = llama.protocol("uniswap")

    assert llama_result.protocol == "Uniswap"
    assert llama_session.calls[0][0] == "GET"
