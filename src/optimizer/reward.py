"""Scalar reward for a post's engagement. Imports canonical weights from
score_weights to prevent silent desync across modules."""
from src.analytics.score_weights import SCORE_WEIGHTS as REWARD_WEIGHTS, engagement_score


def reward(metrics):
    return engagement_score(metrics)
