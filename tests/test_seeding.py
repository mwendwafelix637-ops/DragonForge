from __future__ import annotations

import numpy as np
import pytest
import torch

from src.experiments.seeding import (
    DEFAULT_SEEDS,
    aggregate,
    aggregate_runs,
    compare,
    run_across_seeds,
    set_all_seeds,
)


def test_seeding_makes_torch_reproducible():
    set_all_seeds(42)
    first = torch.randn(20)
    set_all_seeds(42)
    second = torch.randn(20)

    assert torch.equal(first, second)


def test_seeding_makes_numpy_reproducible():
    set_all_seeds(42)
    first = np.random.rand(20)
    set_all_seeds(42)
    second = np.random.rand(20)

    assert np.array_equal(first, second)


def test_different_seeds_give_different_draws():
    set_all_seeds(1)
    first = torch.randn(20)
    set_all_seeds(2)
    second = torch.randn(20)

    assert not torch.equal(first, second)


def test_seeding_covers_weight_initialisation():
    set_all_seeds(7)
    first = torch.nn.Linear(16, 16).weight.detach().clone()
    set_all_seeds(7)
    second = torch.nn.Linear(16, 16).weight.detach().clone()

    assert torch.equal(first, second)


def test_a_single_value_has_zero_spread_and_says_so():
    result = aggregate("accuracy", [0.8])

    assert result.mean == 0.8
    assert result.std == 0.0
    assert result.n == 1


def test_mean_and_standard_deviation_are_computed():
    result = aggregate("accuracy", [0.8, 0.9, 1.0])

    assert result.mean == pytest.approx(0.9)
    assert result.std == pytest.approx(0.1)
    assert result.n == 3
    assert result.stderr == pytest.approx(0.1 / 3 ** 0.5)


def test_aggregating_nothing_is_an_error():
    with pytest.raises(ValueError):
        aggregate("accuracy", [])


def test_none_values_are_dropped():
    result = aggregate("accuracy", [0.8, None, 1.0])

    assert result.n == 2
    assert result.mean == pytest.approx(0.9)


def test_only_shared_numeric_metrics_are_aggregated():
    runs = [
        {"accuracy": 0.8, "forgetting": 0.1, "label": "a", "converged": True},
        {"accuracy": 0.9, "forgetting": 0.2, "label": "b", "converged": False},
    ]

    aggregates = aggregate_runs(runs)

    assert set(aggregates) == {"accuracy", "forgetting"}


def test_metrics_missing_from_one_run_are_skipped():
    runs = [{"accuracy": 0.8, "extra": 1.0}, {"accuracy": 0.9}]

    assert set(aggregate_runs(runs)) == {"accuracy"}


def test_every_seed_is_run_once():
    seen = []

    def run_once(seed):
        seen.append(seed)
        return {"accuracy": 0.5}

    results = run_across_seeds(run_once, seeds=[1, 2, 3])

    assert seen == [1, 2, 3]
    assert results.completed == 3


def test_the_default_is_three_seeds():
    results = run_across_seeds(lambda seed: {"accuracy": 0.5})

    assert results.seeds == list(DEFAULT_SEEDS)
    assert results.aggregates["accuracy"].n == 3


def test_results_are_aggregated_across_seeds():
    accuracies = {1: 0.80, 2: 0.90, 3: 1.00}

    results = run_across_seeds(
        lambda seed: {"accuracy": accuracies[seed]}, seeds=[1, 2, 3]
    )

    assert results.aggregates["accuracy"].mean == pytest.approx(0.9)
    assert results.aggregates["accuracy"].std == pytest.approx(0.1)
    assert results.aggregates["accuracy"].values == [0.8, 0.9, 1.0]


def test_the_sweep_actually_varies_the_seed():
    results = run_across_seeds(
        lambda seed: {"draw": float(torch.randn(1).item())}, seeds=[1, 2, 3]
    )

    assert results.aggregates["draw"].std > 0


def test_the_same_seed_reproduces_the_same_run():
    def run_once(seed):
        return {"draw": float(torch.randn(1).item())}

    first = run_across_seeds(run_once, seeds=[11, 22])
    second = run_across_seeds(run_once, seeds=[11, 22])

    assert first.per_seed == second.per_seed


def test_a_failing_seed_does_not_discard_the_others():
    def run_once(seed):
        if seed == 2:
            raise RuntimeError("diverged")
        return {"accuracy": 0.9}

    results = run_across_seeds(run_once, seeds=[1, 2, 3])

    assert results.completed == 2
    assert "diverged" in results.failures[2]
    assert results.aggregates["accuracy"].n == 2


def test_a_failing_seed_can_abort_the_sweep():
    def run_once(seed):
        raise RuntimeError("diverged")

    with pytest.raises(RuntimeError):
        run_across_seeds(run_once, seeds=[1, 2], stop_on_failure=True)


def test_duplicate_seeds_are_refused():
    with pytest.raises(ValueError):
        run_across_seeds(lambda seed: {"accuracy": 0.5}, seeds=[1, 1, 2])


def test_no_seeds_is_an_error():
    with pytest.raises(ValueError):
        run_across_seeds(lambda seed: {"accuracy": 0.5}, seeds=[])


def test_the_serialised_form_carries_the_spread_and_the_raw_values():
    results = run_across_seeds(
        lambda seed: {"accuracy": seed / 10}, seeds=[1, 2, 3]
    )
    payload = results.to_dict()

    assert payload["completed_runs"] == 3
    assert payload["aggregates"]["accuracy"]["std"] > 0
    assert payload["aggregates"]["accuracy"]["values"] == [0.1, 0.2, 0.3]
    assert set(payload["per_seed"]) == {"1", "2", "3"}


def test_the_headline_reports_a_spread_not_a_bare_number():
    results = run_across_seeds(
        lambda seed: {"accuracy": seed / 10}, seeds=[1, 2, 3]
    )

    assert "+/-" in results.headline("accuracy")
    assert "n=3" in results.headline("accuracy")


def test_comparing_two_sweeps_reports_the_overlap():
    close_a = run_across_seeds(lambda s: {"forgetting": 0.200 + s / 100}, seeds=[1, 2, 3])
    close_b = run_across_seeds(lambda s: {"forgetting": 0.205 + s / 100}, seeds=[1, 2, 3])

    verdict = compare("bdh", close_a, "transformer", close_b, "forgetting")

    assert verdict["overlapping_spread"] is True
    assert verdict["difference"] == pytest.approx(-0.005)


def test_a_clear_separation_is_reported_as_non_overlapping():
    low = run_across_seeds(lambda s: {"forgetting": 0.08 + s / 1000}, seeds=[1, 2, 3])
    high = run_across_seeds(lambda s: {"forgetting": 0.23 + s / 1000}, seeds=[1, 2, 3])

    verdict = compare("bdh", low, "transformer", high, "forgetting")

    assert verdict["overlapping_spread"] is False
    assert verdict["difference_in_pooled_std"] < -10


def test_comparing_an_unmeasured_metric_is_an_error():
    results = run_across_seeds(lambda s: {"accuracy": 0.9}, seeds=[1, 2])

    with pytest.raises(ValueError):
        compare("a", results, "b", results, "forgetting")
