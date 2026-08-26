# Seeds, spread, and what the results actually support

`src/experiments/seeding.py` exists because the comparative claims in this
repository were made from single runs. This document records the gap and what
now closes it.

---

## The problem

`results/summary.json` states:

> BDH retains 90.1% Task A accuracy after Task B training vs 71.6% for
> Transformer

`results/continual/result.json` records the underlying numbers, tagged
`"MEASURED"`, with:

```json
"seeds": [42, 123, 456]
```

The codebase never ran three seeds. The only seeding anywhere was a single line
in the task loader, and it seeded the permutation of the *task*, not the run:

```python
np.random.seed(task_id * 42)
```

Nothing seeded torch, so weight initialisation and batch ordering were
unseeded — which is where most of the run-to-run variance in a training
comparison lives. Nothing ran the experiment more than once, aggregated across
runs, or reported a spread.

So the headline is a single-run difference presented as a replicated result.
The measurement may well be real; the evidence recorded does not establish it.

**The numbers themselves are internally consistent** — 0.73/0.81 = 90.1% and
0.58/0.81 = 71.6%, so "retains" means retention relative to pre-task-B
accuracy, not absolute accuracy. That wording is worth tightening, but it is
not the problem. The problem is `n = 1` described as `n = 3`.

---

## What was added

### `set_all_seeds(seed)`

Seeds `random`, `numpy`, and `torch` (including CUDA), with an optional
cuDNN-deterministic mode. Seeding numpy alone leaves the model's own
initialisation untouched, which is the variance that matters most.

There is a test that a `torch.nn.Linear` initialises identically under the same
seed, because that is the specific thing the old code did not cover.

### `run_across_seeds(run_once, seeds)`

Runs an experiment once per seed, applying the seed before each call, and
aggregates. Defaults to `(42, 123, 456)` — the seeds the results file already
claimed.

A seed that raises is recorded in `failures` and excluded from the aggregate
rather than aborting the sweep. Losing two good runs because a third diverged
is worse than reporting `n = 2` honestly.

### `Aggregate`

Mean, sample standard deviation, standard error, `n`, and **the raw per-seed
values**, which are kept so a reader can see the spread rather than trust a
summary of it. `headline()` formats as `mean +/- std (n=k)`; there is no way to
print a bare mean from it.

A single value yields `std = 0.0` with `n = 1`, so a one-run result is visibly
a one-run result instead of looking like a tight measurement.

### `compare(...)`

Reports the difference between two sweeps against the pooled spread, and
whether the two spreads overlap.

It deliberately does **not** report a p-value. Three seeds cannot support a
significance test, and printing one would repeat the original mistake in a more
sophisticated-looking form. `difference_in_pooled_std` and
`overlapping_spread` give the reader the magnitude and let them judge.

### The global-seed leak in the task loader

`load_permuted_mnist` called `np.random.seed(task_id * 42)`, which reset the
**global** numpy RNG as a side effect of loading data. Any seeding established
before it was silently destroyed. It now uses a local
`np.random.default_rng(...)`, so task permutations stay fixed across seeds —
which is correct, the tasks are the experiment's constant — without touching
global state.

---

## What is still outstanding

The machinery is built and tested (`tests/test_seeding.py`, 24 cases), but
**the published results have not been regenerated**. Doing that requires
training runs, and fabricating aggregates would be a worse version of the
problem this document describes.

Until `results/` is regenerated with `run_across_seeds`, the honest reading of
`summary.json` is: a single-run result, direction plausible, magnitude
unestablished. The `"seeds": [42, 123, 456]` field should be removed or the
runs actually performed.

---

## Known limits

- No significance testing. With three seeds that is the correct choice, but it
  means "BDH is better" remains a qualitative claim.
- Sweeps run sequentially; there is no parallelism across seeds.
- `aggregate_runs` only handles flat scalar metrics. Per-task dictionaries such
  as `forgetting` are not aggregated element-wise.
- Nothing enforces that a comparison used the same seeds for both arms, which
  it should for a paired analysis.
