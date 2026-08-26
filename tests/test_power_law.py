from __future__ import annotations

import numpy as np
import pytest

from src.instrumentation.metrics import (
    POWER_LAW_PLAUSIBLE_P,
    MetricsComputer,
)


@pytest.fixture
def computer() -> MetricsComputer:
    return MetricsComputer({"power_law_bootstrap": 0})


def sample_power_law(alpha: float, k_min: float, size: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return k_min * rng.uniform(size=size) ** (-1.0 / (alpha - 1.0))


def test_a_known_exponent_is_recovered(computer):
    data = sample_power_law(alpha=2.5, k_min=1.0, size=6000, seed=7)

    alpha, k_min, _ = computer._fit_power_law(data)

    assert alpha == pytest.approx(2.5, abs=0.12)
    assert k_min >= 1.0


@pytest.mark.parametrize("true_alpha", [2.0, 2.5, 3.0, 3.5])
def test_exponents_are_recovered_across_the_useful_range(computer, true_alpha):
    data = sample_power_law(alpha=true_alpha, k_min=1.0, size=6000, seed=11)

    alpha, _, _ = computer._fit_power_law(data)

    assert alpha == pytest.approx(true_alpha, rel=0.08)


def test_the_fit_does_not_depend_on_input_order(computer):
    data = sample_power_law(alpha=2.5, k_min=1.0, size=2000, seed=3)
    shuffled = data.copy()
    np.random.default_rng(99).shuffle(shuffled)

    assert computer._fit_power_law(data) == computer._fit_power_law(shuffled)


def test_k_min_is_estimated_not_taken_from_the_minimum(computer):
    rng = np.random.default_rng(5)
    body = rng.uniform(1.0, 10.0, size=3000)
    tail = sample_power_law(alpha=2.5, k_min=10.0, size=3000, seed=6)
    data = np.concatenate([body, tail])

    alpha, k_min, _ = computer._fit_power_law(data)

    assert k_min > data.min() * 2
    assert alpha == pytest.approx(2.5, abs=0.3)


def test_a_degree_regular_graph_does_not_divide_by_zero(computer):
    assert computer._fit_power_law([4.0] * 500) == (None, None, None)


def test_too_few_points_are_refused(computer):
    assert computer._fit_power_law([1.0, 2.0, 3.0]) == (None, None, None)


def test_too_few_distinct_values_are_refused(computer):
    assert computer._fit_power_law([1.0, 2.0] * 100) == (None, None, None)


def test_zero_and_negative_degrees_are_dropped(computer):
    data = list(sample_power_law(2.5, 1.0, 2000, seed=13)) + [0.0, -1.0, 0.0]

    alpha, _, _ = computer._fit_power_law(data)

    assert alpha is not None
    assert np.isfinite(alpha)


def test_an_empty_input_is_refused(computer):
    assert computer._fit_power_law([]) == (None, None, None)


def test_the_returned_exponent_is_above_one(computer):
    data = sample_power_law(alpha=2.2, k_min=3.0, size=3000, seed=21)

    alpha, _, _ = computer._fit_power_law(data)

    assert alpha > 1.0


def test_a_genuine_power_law_is_not_rejected():
    computer = MetricsComputer({"power_law_bootstrap": 120, "power_law_seed": 1})
    data = sample_power_law(alpha=2.5, k_min=1.0, size=800, seed=17)

    _, _, p_value = computer._fit_power_law(data)

    assert p_value >= POWER_LAW_PLAUSIBLE_P


def test_a_narrow_tail_cannot_support_a_power_law_claim(computer):
    rng = np.random.default_rng(23)
    data = np.abs(rng.normal(loc=50.0, scale=5.0, size=800))

    assert computer._fit_power_law(data) == (None, None, None)


def test_exponential_degrees_are_rejected_by_the_bootstrap():
    computer = MetricsComputer({"power_law_bootstrap": 120, "power_law_seed": 1})
    rng = np.random.default_rng(23)
    data = rng.exponential(scale=10.0, size=1500)

    alpha, _, p_value = computer._fit_power_law(data)

    assert alpha is not None
    assert p_value < POWER_LAW_PLAUSIBLE_P


def test_a_tail_spanning_less_than_a_decade_is_refused(computer):
    rng = np.random.default_rng(59)
    data = rng.uniform(100.0, 180.0, size=1000)

    assert computer._fit_power_law(data) == (None, None, None)


def test_the_p_value_is_a_probability():
    computer = MetricsComputer({"power_law_bootstrap": 40, "power_law_seed": 2})
    data = sample_power_law(alpha=2.5, k_min=1.0, size=400, seed=29)

    _, _, p_value = computer._fit_power_law(data)

    assert 0.0 <= p_value <= 1.0


def test_the_bootstrap_is_reproducible_under_a_fixed_seed():
    first = MetricsComputer({"power_law_bootstrap": 40, "power_law_seed": 5})
    second = MetricsComputer({"power_law_bootstrap": 40, "power_law_seed": 5})
    data = sample_power_law(alpha=2.5, k_min=1.0, size=400, seed=31)

    assert first._fit_power_law(data) == second._fit_power_law(data)


def test_the_bootstrap_can_be_switched_off(computer):
    data = sample_power_law(alpha=2.5, k_min=1.0, size=400, seed=37)

    alpha, k_min, p_value = computer._fit_power_law(data)

    assert alpha is not None and k_min is not None
    assert p_value is None


def test_the_ks_distance_is_zero_for_a_perfect_fit(computer):
    alpha, k_min = 2.5, 1.0
    quantiles = (np.arange(1, 2001) - 0.5) / 2000
    exact = k_min * (1.0 - quantiles) ** (-1.0 / (alpha - 1.0))

    ks_stat = computer._power_law_ks(np.sort(exact), k_min, alpha)

    assert ks_stat < 0.01


def test_the_ks_distance_is_large_for_a_wrong_exponent(computer):
    data = np.sort(sample_power_law(alpha=2.5, k_min=1.0, size=2000, seed=41))

    good = computer._power_law_ks(data, 1.0, 2.5)
    bad = computer._power_law_ks(data, 1.0, 5.0)

    assert bad > good * 3
