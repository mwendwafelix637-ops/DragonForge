# DragonForge — Repo Structure & Team Rulebook

## 1. Full Repo Structure

```
DragonForge
│
├── OFFICIAL BDH
│   └── bdh/                         # Official BDH core implementation
│
├── MODEL LAYER
│   └── src/models/                  # Model loaders, architecture wrappers & baselines
│
├── INSTRUMENTATION
│   └── src/instrumentation/        # Internal activation & network analysis utilities
│
├── EXPERIMENTS
│   └── src/experiments/            # Continual learning & long-context reasoning pipelines
│
├── METRICS
│   └── src/instrumentation/metrics.py # Sparsity, modularity, degree & graph metrics
│
├── GRAPH
│   └── src/instrumentation/graph_extractor.py # Node & edge extraction from model weights/activations
│
├── DASHBOARD
│   └── frontend/                   # React client and Express results server
│
├── TRAINING
│   └── scripts/                    # Training and measurement execution scripts
│
└── DOCUMENTATION
    ├── README.md                   # Main project overview & quickstart
    ├── TECHNICAL_DOCS.md           # Comprehensive technical specification & documentation
    └── repo_structure_and_rules.md  # Repository architecture and team workflow rules
```
│   │   └── result.json
│   └── summary.json                 # rolled-up headline finding, written last by run_all.py
│
├── frontend/                        # ==== FULL-STACK SIDE — owned by Aditya ====
│   ├── server/                      # Node/Express
│   │   ├── index.js
│   │   ├── routes/
│   │   │   ├── structure.js         # reads results/structure/*.json
│   │   │   ├── continual.js
│   │   │   ├── reasoning.js
│   │   │   └── summary.js
│   │   └── package.json
│   └── client/                      # React (Vite)
│       ├── src/
│       │   ├── components/
│       │   │   ├── StructureGraph.jsx
│       │   │   ├── TrainingEvolution.jsx
│       │   │   ├── ReasoningBenchmark.jsx
│       │   │   ├── ForgettingChart.jsx
│       │   │   └── Headline.jsx
│       │   ├── App.jsx
│       │   └── main.jsx
│       ├── vite.config.js
│       └── package.json
│
├── scripts/                         # one-off / setup scripts, not part of the pipeline
│   ├── train_small_bdh.py
│   └── extract_and_measure.py
│
├── assets/
│   ├── architecture.png
│   └── showcase.gif                 # or link to demo video
│
└── docs/
    ├── graph_definition.md          # locked graph spec (see §4) — written before any results exist
    ├── research_contract.md         # every claim tagged ESTABLISHED / MEASURED / EXPLORATORY
    └── if_we_had_a_larger_model.md
```

---

## 2. The Core Rule

**`results/` is the only thing that connects the two sides of this project.**

The ML side writes JSON/CSV into `results/`. The frontend side only ever *reads* from `results/`. Nobody imports Python from JavaScript or vice versa. If you ever find yourself wanting to call ML code directly from the frontend, or writing frontend logic into a Python file — stop, that means the file structure is being violated.

This means: **the ML team can rerun experiments while the frontend team is still building UI, and nothing breaks, as long as the JSON shape stays the same.**

---

## 3. File Ownership — who touches what

| Folder | Owner | Others may... |
|---|---|---|
| `src/` | ML engineers | ...read to understand output format, never edit |
| `frontend/` | Aditya (full-stack) | ...ML team never touches this folder |
| `results/` | Written by ML side, read by frontend | Nobody hand-edits files here, ever — always regenerate via `run_all.py` |
| `docs/` | Whoever is writing that section | Shared — but one person edits at a time, see §6 |
| `configs/default.yaml` | ML side, but frontend can read it for display labels | Any change gets flagged in the team chat, since it can change output shape |

If two people are touching the same file at the same time regularly, that's a sign the boundary is wrong — split the file, don't share it.

---

## 4. The JSON Contract (lock this FIRST, before writing pipeline code)

Every file in `results/` follows a fixed shape. Agree on this as a team before anyone builds against it — changing it later means changing code on both sides.

```json
// results/structure/checkpoint_<N>.json
{
  "step": 3,
  "modularity": 0.41,
  "modularity_random_control": 0.13,
  "sparsity": 0.82,
  "degree_distribution": [1, 1, 2, 3, 5, 8, ...],
  "clustering_coefficient": 0.27,
  "timestamp": "2026-08-10T14:32:00Z"
}
```

```json
// results/continual/result.json
{
  "task_a_before": 0.80,
  "task_a_after": 0.73,
  "task_b_after": 0.76,
  "forgetting": 0.07,
  "baseline_transformer": { "task_a_before": 0.81, "task_a_after": 0.58, "forgetting": 0.23 },
  "tag": "MEASURED",
  "seeds": [1, 2, 3]
}
```

```json
// results/reasoning/result.json
{
  "task_name": "babilong-style-task-1",
  "bdh_accuracy_mean": 0.72,
  "bdh_accuracy_std": 0.04,
  "transformer_accuracy_mean": 0.68,
  "transformer_accuracy_std": 0.03,
  "seeds": [1, 2, 3],
  "tag": "MEASURED"
}
```

```json
// results/summary.json — written last, after all experiments finish
{
  "headline": "Structure partially predicts behavior: modularity correlates with reduced forgetting, no clear link to reasoning accuracy",
  "structure_finding": { "claim": "...", "tag": "MEASURED" },
  "continual_finding": { "claim": "...", "tag": "MEASURED" },
  "reasoning_finding": { "claim": "...", "tag": "PARTIALLY_SUPPORTED" }
}
```

**Rule: any field renamed, removed, or retyped in these schemas requires a one-line message to the whole team before you push.** Silent schema changes are the #1 way integrations break under deadline pressure.

---

## 5. Graph Definition — locked before results exist

Per your own plan doc: node/edge/weight/threshold definitions go in `docs/graph_definition.md` and are written and agreed **before** anyone looks at real output. Once `checkpoint_0.json` exists, this file does not change. If you discover the definition needs to change later, that's a new experiment, not a silent edit — document why in the same file rather than overwriting the original decision.

---

## 6. Working Rules (the actual "don't get tangled" part)

1. **Never hand-edit anything in `results/`.** If a number looks wrong, fix the code that generated it and rerun. A hand-edited result file is indistinguishable from a fabricated one, and it will bite you the moment someone reruns the pipeline and gets a different answer.

2. **Commit early, commit often, small commits.** A single end-of-day mega-commit is how merge conflicts eat your remaining hours. Push after every working unit (one metric, one component, one route).

3. **One branch per person, merge to `main` only when it runs.** `git checkout -b aditya/structure-graph`, `git checkout -b <name>/continual-experiment`. Never commit directly to `main` on this timeline — a broken `main` blocks everyone.

4. **The frontend never blocks on the ML side finishing.** Build against fixture/dummy JSON matching the agreed schema (§4) first. Swap in real `results/` files the moment they exist. This is why locking the schema in step 0 matters more than anything else in this document.

5. **`notebooks/` is scratch space, not source.** Nothing in the actual pipeline (`run_all.py`, routes, components) may depend on a notebook. If code in a notebook works, move it into `src/` properly before anyone relies on it.

6. **`configs/default.yaml` is the only place magic numbers live.** Model size, number of seeds, checkpoint frequency, task names — if it's a number or setting that might change, it goes in the config, not hardcoded in a script. This is what lets the frontend read config for display labels without duplicating values.

7. **Docs get updated the same day the underlying thing changes.** If the graph definition changes, `docs/graph_definition.md` changes that day. If a claim's tag changes from EXPLORATORY to MEASURED because you got a result, `docs/research_contract.md` changes that day. Docs written the night before submission from memory are where inconsistencies with your actual slides/dashboard creep in.

8. **Dashboard never ships placeholder data.** If an experiment isn't done, that panel is either hidden or explicitly labeled "pending" — never a fake number sitting in a chart. This matches the honesty framing across the whole project; a judge who spots one fabricated-looking number will start doubting all your real ones.

---

## 7. Daily Sync Checklist (5 minutes, not a meeting)

- [ ] Does `results/` have new files since yesterday? What changed?
- [ ] Did any JSON schema change? (If yes — was it announced before the push?)
- [ ] Is anything in `main` currently broken?
- [ ] What's each person touching next, so nobody duplicates work?