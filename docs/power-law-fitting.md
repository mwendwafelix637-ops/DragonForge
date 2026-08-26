# Fitting power laws to degree distributions

`MetricsComputer._fit_power_law` reports whether a graph's degree distribution
is scale-free. This document records what the original implementation got
wrong, what replaced it, and why each guard exists.

---

## What was wrong

The original was the right estimator applied incorrectly, in four ways.

### 1. `k_min` was taken as the smallest degree

```python
k_min = deg_array.min()
alpha = 1 + n / np.sum(np.log(deg_array / k_min))
```

A power law describes the **tail** of a distribution, not the whole of it.
Clauset–Shalizi–Newman estimate `k_min` — the degree above which the scaling
actually holds — by minimising the KS distance. Forcing it to the minimum fits
the power law over the body as well, where it does not hold, and drags the
exponent down.

The effect is not marginal. On a synthetic distribution with a uniform body on
[1, 10] and a genuine α = 2.5 tail above 10:

| Method | α recovered | Error |
|---|---|---|
| `k_min` = data minimum | **1.444** | 42% |
| `k_min` estimated by KS | **2.529** | 1% |

Pure synthetic power-law data hides the bug, because there the whole dataset
*is* the tail. Real degree distributions always have a body.

### 2. The KS statistic compared unsorted data to a sorted CDF

```python
empirical_cdf = np.arange(1, n+1) / n
theoretical_cdf = 1 - (deg_array / k_min) ** (-(alpha - 1))
ks_stat = np.max(np.abs(empirical_cdf - theoretical_cdf))
```

`empirical_cdf` is a monotonic ramp; it only lines up with `deg_array` if that
array is sorted ascending. It comes out of `graph.degree()` in node order, so
the two were paired arbitrarily and `ks_stat` measured nothing.

Demonstrated on the same data, sorted versus shuffled:

```
p(sorted)   = 0.2420
p(shuffled) = 0.0000
```

Same distribution, same fit, opposite conclusion, depending on the order nodes
happened to be stored in.

### 3. The p-value was not a p-value

`exp(-2n·KS²)` is an asymptotic form for a KS test against a **fully specified**
distribution. Here the distribution's parameters were estimated from the same
data, which invalidates it. Clauset et al. use a semi-parametric bootstrap
instead.

Its direction was also the opposite of what the code's use implied: for a
goodness-of-fit test, a *small* p-value **rejects** the power law. Nothing in
the codebase interpreted it that way.

### 4. Degree-regular graphs divided by zero

If every degree is equal, `sum(log(k/k_min))` is exactly 0 and α is `inf`.
There was no guard; the bare `except:` around the call swallowed the
`RuntimeWarning` and silently returned `None`, so the failure was invisible.

---

## What replaced it

### `k_min` chosen by minimising the KS distance

Every distinct degree is a candidate (capped at `MAX_KMIN_CANDIDATES` for
cost). For each, α is fitted to the tail above it and the KS distance measured;
the `k_min` with the smallest distance wins. `k_min` is now reported alongside
α, because an exponent without the range it applies to is uninterpretable.

### A correctly paired, two-sided KS statistic

The tail is sorted, and the empirical CDF is compared at both `i/n` and
`(i-1)/n` — the standard two-sided form, which avoids the half-step bias of
using only one.

### A semi-parametric bootstrap p-value

Each synthetic dataset keeps the observed body below `k_min` and draws a fresh
tail from the fitted power law, then is **refitted from scratch, including
re-selecting `k_min`**. Refitting is what makes the comparison fair: the
observed KS distance benefited from `k_min` being tuned to this data, so the
synthetic ones must get the same advantage.

`p` is the fraction of synthetic fits at least as bad as the observed one.
**A small p-value rejects the power law.** `power_law_plausible` exposes the
`p >= 0.10` convention from the paper so nobody has to remember the direction.

### Guards that refuse to answer

Three conditions make a power-law claim unsupportable, and the function returns
`None` rather than a number:

| Guard | Threshold | Why |
|---|---|---|
| Sample size | `n >= 10`, distinct values `>= 4` | Nothing to fit |
| Tail size | `>= 50` and `>= 10%` of the data | Clauset et al. recommend 50 for stable estimates; a claim about 5% of nodes is not a structural claim about the network |
| Scaling range | tail must span `>= 1` decade | **The important one** |

The scaling-range guard is what the original most needed. Without it, on
degrees drawn from a normal distribution, the fit happily returned:

```
alpha = 27.9   k_min = 56.4   KS = 0.066   tail = 80 points   (data range 30.7 - 66.0)
```

α = 27.9 is physically meaningless, and the tail spans a factor of 1.17 — a
twelfth of a decade. Any distribution looks like a power law over a narrow
enough range, so KS distance being small says nothing. Worse, the bootstrap
*cannot* catch this: it generates synthetic data from that same degenerate fit,
so the synthetic KS distances match, and the p-value comes back a comfortable
0.32.

With the guard, normal degrees are refused outright, while an exponential
distribution — which does span decades, and so is a fair test of the
bootstrap — is correctly rejected with `p = 0.0`, and a genuine power law
passes with `p = 0.73`.

---

## Tests

`tests/test_power_law.py`, 22 cases:

- α is recovered within 8% across the useful range (2.0 to 3.5).
- The fit is **identical for shuffled input** — the ordering bug cannot return.
- `k_min` is estimated above the data minimum on body-plus-tail data.
- Degree-regular graphs, too few samples, too few distinct values, and empty
  input are refused rather than crashing.
- Genuine power laws are not rejected; exponential data is; narrow-range data
  is refused.
- The bootstrap is reproducible under a fixed seed.
- The KS distance is ~0 for an exact fit and much larger for a wrong exponent.

---

## Known limits

- The continuous MLE is used. Degrees here are edge-weight sums, so they are
  genuinely continuous; for unweighted integer degrees the discrete estimator
  would be more appropriate.
- The bootstrap defaults to 100 iterations, which resolves p to about 0.01.
  Clauset et al. suggest 2500 for two decimal places.
- Rejecting a power law does not say what the distribution *is*. A likelihood
  ratio test against log-normal and exponential alternatives is the usual next
  step, and is not implemented.
- `k_min` candidates are subsampled above 60 distinct values, so on very large
  graphs the chosen `k_min` is near-optimal rather than optimal.
