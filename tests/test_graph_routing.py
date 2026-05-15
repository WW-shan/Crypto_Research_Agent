def test_graph_routes_from_scan_to_hypothesis():
    from crypto_alpha_agent.orchestrator import build_graph

    graph = build_graph()
    state = graph.invoke({"mode": "research"})
    assert "opportunities" in state


def test_graph_rejection_path_loops_back_to_hypothesis_generation():
    from crypto_alpha_agent.orchestrator import build_graph

    graph = build_graph()
    state = graph.invoke({"mode": "research", "force_rejection_once": True})

    assert state["trace"].count("generate_hypothesis") == 2
    assert state["rejected_hypotheses"] == 1


def test_graph_critique_path_loops_back_to_strategy_coder():
    from crypto_alpha_agent.orchestrator import build_graph

    graph = build_graph()
    state = graph.invoke({"mode": "research", "force_critique_once": True})

    assert state["trace"].count("code_strategy") == 2
    assert state["critique_revisions"] == 1


def test_graph_human_checkpoint_marks_approval_pause():
    from crypto_alpha_agent.orchestrator import build_graph

    graph = build_graph()
    state = graph.invoke({"mode": "research", "require_human_approval": True})

    assert state["approval_required"] is True
    assert state["trace"][-1] == "human_checkpoint"
    assert "proposal_finalized" not in state
