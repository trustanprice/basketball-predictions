"""Transparent z-score composite ratings: player power rankings + coaching eval.

Consumes backend.live_client and backend.win_model output; makes no HTTP calls
itself. See backend/AGENTS.md's ratings/ conventions — every number here must be
traceable by hand to formula + raw inputs + z-scores + weights.
"""
