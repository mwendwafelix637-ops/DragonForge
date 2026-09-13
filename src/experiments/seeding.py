import logging
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import torch

logger = logging.getLogger(__name__)

DEFAULT_SEEDS = (42, 123, 456)


def set_all_seeds(seed: int, deterministic: bool = False) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    if deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


@dataclass(frozen=True)
class Aggregate:
    metric: str
    values: List[float]
    mean: float
    std: float
    n: int

    @property
    def stderr(self) -> float:
        return self.std / (self.n ** 0.5) if self.n else 0.0

    def summary(self, places: int = 4) -> str:
        return f"{self.mean:.{places}f} +/- {self.std:.{places}f} (n={self.n})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "mean": self.mean,
            "std": self.std,
            "stderr": self.stderr,
            "n": self.n,
            "values": self.values,
        }


def aggregate(metric: str, values: Sequence[float]) -> Aggregate:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        raise ValueError(f"No values to aggregate for {metric!r}")

    return Aggregate(
        metric=metric,
        values=numbers,
        mean=statistics.fmean(numbers),
        std=statistics.stdev(numbers) if len(numbers) > 1 else 0.0,
        n=len(numbers),
    )


def aggregate_runs(
    runs: Sequence[Dict[str, Any]], metrics: Optional[Sequence[str]] = None
) -> Dict[str, Aggregate]:
    if not runs:
        raise ValueError("No runs to aggregate")

    if metrics is None:
        shared = set(runs[0])
        for run in runs[1:]:
            shared &= set(run)
        metrics = sorted(
            name
            for name in shared
            if all(isinstance(run[name], (int, float)) for run in runs)
            and not any(isinstance(run[name], bool) for run in runs)
        )

    return {name: aggregate(name, [run[name] for run in runs]) for name in metrics}


@dataclass
class SeededResults:
    seeds: List[int]
    per_seed: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    aggregates: Dict[str, Aggregate] = field(default_factory=dict)
    failures: Dict[int, str] = field(default_factory=dict)

    @property
    def completed(self) -> int:
        return len(self.per_seed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seeds": self.seeds,
            "completed_runs": self.completed,
            "per_seed": {str(seed): run for seed, run in self.per_seed.items()},
            "aggregates": {
                name: value.to_dict() for name, value in self.aggregates.items()
            },
            "failures": {str(seed): error for seed, error in self.failures.items()},
        }

    def headline(self, metric: str, places: int = 4) -> str:
        if metric not in self.aggregates:
            return f"{metric}: not measured"
        return f"{metric}: {self.aggregates[metric].summary(places)}"


def run_across_seeds(
    run_once: Callable[[int], Dict[str, Any]],
    seeds: Sequence[int] = DEFAULT_SEEDS,
    metrics: Optional[Sequence[str]] = None,
    deterministic: bool = False,
    stop_on_failure: bool = False,
) -> SeededResults:
    seeds = list(seeds)
    if not seeds:
        raise ValueError("At least one seed is required")
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"Seeds must be distinct, got {seeds}")

    results = SeededResults(seeds=seeds)

    for seed in seeds:
        set_all_seeds(seed, deterministic=deterministic)
        try:
            results.per_seed[seed] = run_once(seed)
        except Exception as error:
            logger.exception("Seed %s failed", seed)
            results.failures[seed] = f"{type(error).__name__}: {error}"
            if stop_on_failure:
                raise

    if results.per_seed:
        results.aggregates = aggregate_runs(
            list(results.per_seed.values()), metrics=metrics
        )

    return results


def compare(
    label_a: str,
    results_a: SeededResults,
    label_b: str,
    results_b: SeededResults,
    metric: str,
) -> Dict[str, Any]:
    if metric not in results_a.aggregates or metric not in results_b.aggregates:
        raise ValueError(f"{metric!r} was not measured in both sweeps")

    first, second = results_a.aggregates[metric], results_b.aggregates[metric]
    difference = first.mean - second.mean
    pooled = ((first.std ** 2 + second.std ** 2) / 2) ** 0.5

    return {
        "metric": metric,
        label_a: first.to_dict(),
        label_b: second.to_dict(),
        "difference": difference,
        "pooled_std": pooled,
        "difference_in_pooled_std": (difference / pooled) if pooled > 0 else None,
        "overlapping_spread": abs(difference) < (first.std + second.std),
        "note": (
            f"{first.n} and {second.n} seeds. Too few for a significance test; "
            "the spread is reported so the reader can judge."
        ),
    }
