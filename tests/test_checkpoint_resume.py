from crypto_alpha_agent.checkpointing import create_checkpointer, create_thread_config
from crypto_alpha_agent.orchestrator import build_checkpointed_graph


def approve_current_state(graph, config):
    snapshot = graph.get_state(config)
    graph.update_state(config, {**snapshot.values, "human_approved": True})


def test_interrupted_run_resumes_from_human_checkpoint_with_same_thread_id():
    checkpointer = create_checkpointer()
    graph = build_checkpointed_graph(checkpointer=checkpointer, interrupt_before=["human_checkpoint"])
    config = create_thread_config("resume-thread")

    paused = graph.invoke({"mode": "research", "require_human_approval": True}, config)

    assert paused["trace"][-1] == "risk_guard"
    assert graph.get_state(config).next == ("human_checkpoint",)

    approve_current_state(graph, config)
    resumed = graph.invoke(None, config)

    assert resumed["trace"][-2:] == ["human_checkpoint", "proposal_finalize"]
    assert resumed["approval_required"] is False
    assert resumed["proposal_finalized"] is True
    assert graph.get_state(config).next == ()


def test_filesystem_checkpointer_recovers_interrupted_run_after_restart(tmp_path):
    checkpoint_path = tmp_path / "workflow-checkpoints.pkl"
    config = create_thread_config("durable-thread")

    first_graph = build_checkpointed_graph(
        checkpointer=create_checkpointer(checkpoint_path),
        interrupt_before=["human_checkpoint"],
    )
    first_graph.invoke({"mode": "research", "require_human_approval": True}, config)
    assert first_graph.get_state(config).next == ("human_checkpoint",)

    restarted_graph = build_checkpointed_graph(checkpointer=create_checkpointer(checkpoint_path))
    assert restarted_graph.get_state(config).next == ("human_checkpoint",)

    approve_current_state(restarted_graph, config)
    resumed = restarted_graph.invoke(None, config)

    assert resumed["trace"][-2:] == ["human_checkpoint", "proposal_finalize"]
    assert resumed["proposal_finalized"] is True
