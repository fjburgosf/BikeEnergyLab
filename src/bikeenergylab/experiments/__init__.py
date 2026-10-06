"""Reproducible scientific experiments."""

from .benchmark import run_benchmark
from .synthetic import generate_observations

__all__ = ["run_benchmark", "generate_observations"]
