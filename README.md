# IntelliTask

**An Explainable Knowledge Graph-Driven Hybrid Recommender for Intelligent Task Allocation in Distributed Onboarding Operations.**

IntelliTask is a Flask prototype in which supervisors create tasks, review recommendations, and assign workers. Workers sign in to view assignments and mark them complete. Recommendations use saved models built from real NetEaseCrowd observations.

NetEaseCrowd is a proxy research dataset for this project. Its worker histories do not establish real onboarding qualifications or accuracy on KYC, SIM registration, or M-PESA tasks.

## Current integration

```text
Supervisor opens a task
  -> Flask recommendation route
  -> HybridRecommendationService
  -> NetEaseRecommendationService
  -> explicit skill-to-capability mapping and eligible worker selection
  -> ml.src.recommender.recommend_agents
  -> saved content, collaborative, and knowledge-graph features
  -> ranked workers and explanations rendered in the webpage
  -> supervisor chooses a worker
  -> assignment and workload saved together
  -> worker views and completes the assignment
```

The active hybrid uses **10% content, 50% collaborative, and 40% knowledge graph**. It loads saved artifacts rather than retraining during page requests. Knowledge-graph features and explanation evidence are precomputed from the saved training graph.

The service checks source-worker bindings, recorded capabilities, and website availability. The assignment route checks task ownership, the form token, current eligibility, and duplicate assignment conditions. Workload is displayed but is not a component of the active website ranking. Completing a website task does not automatically retrain the model.

The supervisor's dataset overview reads training records directly. It is a worker-history preview, not a task-specific recommendation ranking.

## Data and provenance

Source: [official NetEaseCrowd dataset repository](https://github.com/fuxiAIlab/NetEaseCrowd-Dataset).

The retained experiment uses source partitions 1, 6, and 11, containing 1,203,264 raw observations. The selected sample contains **121,201 observations, 17,987 tasks, and 1,653 workers**. This is a subset of the public dataset, not the complete dataset.

| Split | Tasks | Observations |
|---|---:|---:|
| Training | 12,473 | 85,647 |
| Validation | 2,018 | 12,316 |
| Test | 2,699 | 17,137 |
| Purged at temporal boundaries | 797 | 6,101 |

A successful recorded response means the worker's answer equals the dataset ground truth. Historical features and the graph use training outcomes only. Source files, license, and hash manifest are retained in `ml/data/raw/netease/`; processed records and splits are in `ml/data/netease/`. Preserve the source attribution and license when redistributing the dataset.

### Dataset history versus website activity

- Original worker IDs, capability codes, task IDs, and recorded outcomes come from NetEaseCrowd.
- Some imported accounts and saved display artifacts still contain synthetic names and Kenyan locations. These are demonstration attributes, not source identities or model evidence. The dataset overview displays original worker IDs.
- Website accounts, availability, current workload, and assignments are local application records.
- `ml/config/onboarding_capability_mapping.json` currently maps **KYC Verification to capability 56 for demonstration only**. The dataset does not establish that capability 56 means KYC. Other unmapped requirements return an explanatory message instead of recommendations.
- Database IDs are mapped explicitly to source-worker IDs in the local `instance/netease_agent_bindings.json`. This file belongs to its database and must not be copied onto an unrelated database.

## Evaluation

The benchmark ranks the observed participants for each held-out source task. Top-1 success measures whether the first-ranked participant answered that source task correctly. It does not measure website reliability, outcomes for unobserved workers, or onboarding accuracy.

| Model | Top-1 success | MAP@3 |
|---|---:|---:|
| Content only | 69.248% | 62.635% |
| Collaborative only | 80.289% | 72.579% |
| Knowledge graph only | 80.289% | 72.474% |
| Historical quality baseline | **80.511%** | **74.511%** |
| Preserved legacy hybrid | 80.289% | 74.331% |
| Current knowledge-graph hybrid | 79.881% | 72.093% |

The current hybrid does not outperform the historical-quality baseline. Its weights were selected using validation MAP@3 under a positive-weight constraint for all three components. The test split had already been inspected during earlier project work, so this architecture comparison is retrospective, not a new blind evaluation.

See [the evaluation report](ml/reports/VERIFIED_RESULTS.md), [machine-readable results](ml/reports/final_evaluation.json), and notebook 06 for details. Older ML package notes about integration being pending describe the earlier delivery stage; the integration status above describes the current Flask application.

## Project structure

```text
app/                 Flask routes, services, models, templates, and styles
ml/config/           Explicit demonstration capability mapping
ml/data/             Source data, processed observations, and provenance
ml/models/netease/   Saved models, features, graph, and source profiles
ml/notebooks/        Six research notebooks with saved outputs
ml/src/              Training, evaluation, explanations, and inference
ml/salesmesh_ml/     Retained implementation needed for baseline comparisons
ml/reports/          Metrics and figures
ml/tests/            ML package tests
scripts/             Import preview, migration, and demo login utilities
tests/               Flask application tests
instance/            Local database, backups, and bindings (not committed)
config.py
requirements.txt
run.py
seed.py
```

The older top-level Jira and synthetic experiment folders have been removed from the active working tree and preserved separately by the project owner. They are not inputs to the current NetEase integration.

## Fresh installation (Windows PowerShell)

Use Python 3.13 (the version used for the verified application run). Clone the branch containing this integration:

```powershell
git clone --branch codex/netease-integration https://github.com/Sagooparneet/task-allocation-recommender.git
cd task-allocation-recommender
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed.py --instance-dir instance/netease_setup_test --check-only
python seed.py --instance-dir instance/netease_setup_test
python run_netease_test.py
```

The setup prompts for a supervisor name, email, and password of at least 12 characters. Password input is hidden and only its hash is stored. Open `http://127.0.0.1:5001/auth/login` and use that account. The supervisor name/email are user-provided application account information, not NetEase attributes.

Setup creates 1,653 worker accounts labelled by original source ID, four capability skills, and one supervisor. It creates no tasks or assignments and no administrator account. Workers without training history have an unknown success rate. Source profiles have no invented locations or personal names. Worker logins are disabled until explicitly configured for a local demonstration.

The destination folder must not exist. Setup refuses to overwrite an existing installation. If interrupted, preserve the partial folder for inspection and use a new destination only after investigating the error. Do not delete or reset your working database to rerun setup.

The runner uses `instance/netease_setup_test` explicitly, a separate session cookie, port 5001, and debug disabled. Its random session secret changes on restart, requiring users to sign in again. Do not reuse a binding file with a different database. `setup_complete.json` marks successful initialisation.

### Try a recommendation

1. Sign in as the supervisor and choose Create Task.
2. Choose Other / New Task Type and enter `NetEase capability 56`.
3. Enter a description and a location such as `Online` for this local website task.
4. Select only `NetEase capability 56` as the required skill.
5. Save and open recommendations. Worker labels use original NetEase IDs.

The required skill selection drives recommendation eligibility; the task title alone does not. The new installation has a local mapping from each original capability label to the same source code. It does not use the legacy KYC demonstration mapping. Website-created tasks are not additional NetEase observations.

### Existing integrated installation

For the original local website, activate the existing environment and run `python run.py`. It continues using `instance/task_allocation.db` and its matching bindings. Its KYC demonstration mapping remains the fallback when no installation-specific configuration exists.

The scripts under `scripts/` are retained migration utilities for the original installation. In particular, `import_netease_agents.py` assumes the original seven-task migration state, and `enable_demo_agent_login.py` targets a verified database/source-ID pair from that migration. Do not run these as the fresh-installation procedure. Use `seed.py` instead.

### Dependencies and deployment boundary

The root `requirements.txt` lists the application and test dependencies with versions verified in the working Python 3.13 environment. It omits unrelated packages from the previous full environment export. A clean online dependency installation has not yet been independently verified.

Research notebook reproduction uses its own isolated environment and `ml/requirements-notebooks.txt`. Its historical NetworkX pin differs from the application environment; do not combine both dependency sets in one environment. Saved artifact inference does not rebuild the graph.

This is a local academic prototype. The original `run.py` enables debug mode, and `config.py` retains a development secret. Do not expose that runner publicly. Production deployment requires a separate configuration and security review.

## Research notebooks

The six notebooks are under `ml/notebooks/`:

1. `01_netease_data_preparation.ipynb`
2. `02_content_based_filtering.ipynb`
3. `03_collaborative_filtering.ipynb`
4. `04_knowledge_graph.ipynb`
5. `05_hybrid_recommender.ipynb`
6. `06_final_evaluation.ipynb`

Saved outputs can be viewed without executing them. Reproduction instructions and notebook dependencies are included in the ML package. Run notebooks in numerical order in an isolated research environment; executing them can regenerate model artifacts and reports.

## Tests and verification status

From the project root:

```powershell
python -m pytest ml/tests -q
python -m pytest tests -q
```

Verification on 23 October 2026:

- Combined application and ML tests: **26 passed**, with 14 SQLAlchemy legacy-API warnings.
- Fixtures use temporary databases and installation-specific worker bindings; they do not write to the running website database.
- Tests cover login, task validation, NetEase recommendation output, availability filtering, assignment tokens, supervisor ownership, duplicate assignment, completion, and worker permissions.
- The original website's manually exercised assignment/completion flow completed task 6 with one assignment and returned its worker workload to zero.
- The new installation created 1,653 correctly mapped workers, one supervisor, zero tasks, and zero assignments at initialisation. The user verified login and source-ID recommendations on port 5001.

These checks establish the tested prototype workflows, not full production readiness or onboarding prediction accuracy.
