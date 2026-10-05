# DragonForge

DragonForge is being built as a secure, modular market-analysis, research, charting, and decision-support platform. It is not a broker or trading bot and contains no order execution.

The current product foundation is in [platform_api](platform_api/README.md): a FastAPI service, PostgreSQL schema and migrations, owner bootstrap, authentication/2FA foundations, owner setup controls, and a React owner console. This is Phase 1 work, not a production-ready launch; public member registration and market-data integrations intentionally remain disabled/unconfigured.

To run the platform API and client locally, follow the setup in [platform_api/README.md](platform_api/README.md).

## Existing BDH research project

The repository also retains its earlier NeuroLens research dashboard and BDH experiment code. Its results are research artifacts, not DragonForge financial-market analysis or live market data.
The legacy BDH experiment scripts depend on model adapters that are not present in this checkout; they are separate from the active DragonForge platform.

**One-sentence claim:**  
We instrument a real small BDH (Dragon Hatchling) model, measure its internal interaction structure, and connect those measurements to controlled experiments on continual learning and long-context reasoning.

## Problem / Research Question

BDH makes distinctive claims about sparse, structured neural computation and its relationship to reasoning and continual learning. Most public discussion of these claims remains high-level.  

**NeuroLens asks:**  
Can we take a real (small) BDH model, open it up, measure the structural properties it claims, and test whether those properties coincide with interesting behavioral outcomes?

## Architecture / Evaluation Flow

```text
Real BDH Model
      │
      ▼
 Instrumentation
 (Graph extraction + Structural metrics)
      │
      ├──► Continual Learning Experiment
      └──► Long-context Reasoning Experiment
      │
      ▼
 Structure ↔ Behavior Dashboard
```

![Architecture Diagram](assets/architecture.png)

## Repository Structure

```text
DragonForge
│
├── OFFICIAL BDH
│   └── bdh/                         # Official BDH core implementation
│
├── INSTRUMENTATION
│   └── src/instrumentation/        # Network instrumentation framework
│
├── EXPERIMENTS
│   └── src/experiments/            # Continual learning & reasoning tasks
│
├── METRICS
│   └── src/instrumentation/metrics.py # Structural & network metrics
│
├── GRAPH
│   └── src/instrumentation/graph_extractor.py # Graph extractor implementation
│
├── DASHBOARD
│   └── frontend/                   # DragonForge owner console; legacy results API
│
├── TRAINING
│   └── scripts/                    # Training and experiment runner scripts
│
└── DOCUMENTATION
    ├── README.md                   # Main project overview & quickstart
    ├── TECHNICAL_DOCS.md           # Technical documentation
    └── repo_structure_and_rules.md  # Repository guidelines & rules
```

## How to Run

The active DragonForge owner console and API setup are documented in [platform_api/README.md](platform_api/README.md). The old NeuroLens results server is separate and documented in [frontend/README.md](frontend/README.md); it is not the backend for the DragonForge console.

## Proof

### Structural Measurements (MEASURED)

- **Sparsity**
- **Modularity**
- **Degree distribution**

*(Insert key numbers + plots here)*

### Continual Learning (MEASURED)

| Model | Task A Before | Task A After | Forgetting |
|-------|--------------|--------------|------------|
| BDH   | xx%          | xx%          | xx%        |
| Transformer | xx%    | xx%          | xx%        |

### Long-context Reasoning (MEASURED)

| Model | Accuracy |
|-------|----------|
| BDH   | xx%      |
| Transformer | xx%  |

## Technology / Research Anchor

- **Architecture:** Pathway BDH (Dragon Hatchling) – public implementation
- **Commit / Config:** [add commit hash and config used]
- **Focus areas:** Sparse activity, interaction structure, continual learning, long-horizon behavior
- **Baseline:** Small Transformer (matched approximately on scale where possible)

## Claim Labels

| Claim | Type |
|-------|------|
| BDH has sparse positive activations | ESTABLISHED |
| Specific modularity / degree statistics | MEASURED |
| Relationship between structure and retention | EXPLORATORY |
| Performance on our continual learning setup | MEASURED |

## Limitations

- Experiments are conducted on a small BDH model. Results may not hold at larger scale.
- Graph definition (nodes/edges) is one reasonable choice among several possible definitions.
- Statistical power is limited (few seeds).
- We do not claim causality between structure and behavior — only association.
- Long-context task is controlled and simplified for feasibility.

## If We Had Access to a Larger BDH Model

We would repeat the same experimental protocol with the following changes:

- Use the larger publicly available (or released) BDH model.
- Keep the exact same structural metrics (sparsity, modularity, degree distribution).
- Keep the exact same continual learning sequence and long-context task definition.
- Increase number of seeds.
- Compare against stronger Transformer baselines of similar scale.

**Result that would support our current direction:**  
Stronger modularity / sparsity accompanied by clearly lower forgetting and better long-context accuracy than matched Transformers.

**Result that would challenge it:**  
Similar or worse behavioral metrics despite the claimed structural properties appearing.

## Team Contributions

- [Name] — ...
- [Name] — ...

## Demo & Showcase

- Full demo: [link]
- Showcase clip (20-30s): [link to video/GIF]

---

NeuroLens turns BDH's structural claims into measurable experiments and makes the investigation visible.