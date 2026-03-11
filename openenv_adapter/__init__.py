"""
OpenEnv adapter for arc-witness-envs.

Wraps ARC-AGI-3 SDK games (ARCBaseGame) as OpenEnv environments,
enabling RL training via OpenEnv's client-server protocol while
keeping full ARC-AGI-3 compatibility.
"""

from .models import WitnessAction, WitnessObservation, WitnessGameAction
