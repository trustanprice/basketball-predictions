from win_model.ensemble_experiment import run_experiment


def test_run_experiment_reports_a_real_comparison():
    """Full end-to-end run -- slower than the rest of the suite, but this is
    the actual validation backend/AGENTS.md and model_metadata.json cite, so
    it needs to keep working, not just be trusted from memory."""
    result = run_experiment()
    assert result["gbm_walk_forward_mae"] > 0
    assert result["knn_walk_forward_mae"] > 0
    assert result["ensemble_walk_forward_mae"] > 0
    assert result["single_best_model"] in ("gbm", "knn")
    assert isinstance(result["improves_mae"], bool)
    # Documents the actual finding at the time this was written -- if a future
    # change flips this, the honest thing is to update the finding (both here
    # and in train.py's metadata), not to treat this assertion as sacred.
    assert result["improves_mae"] is False
