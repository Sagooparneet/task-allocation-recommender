# IntelliTask

**An Explainable Knowledge Graph-Driven Hybrid Recommender for Intelligent Task Allocation in Distributed Onboarding Operations.**

IntelliTask is a Flask prototype in which supervisors create tasks, review recommendations, and assign workers. The worker workflow supports viewing assignments and marking them complete after worker login has been explicitly enabled. Fresh dataset accounts have login disabled. Recommendations use saved models built from real NetEaseCrowd observations.

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
- Local SQLite installations map database IDs to source-worker IDs in `instance/netease_agent_bindings.json`. This file belongs to its database and must not be copied onto an unrelated database. The PostgreSQL production entry point instead reads mappings from the `worker_source_bindings` database table and maps original capability labels directly to their source codes.

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
scripts/             Setup, migration, verification, and legacy demo utilities
migrations/          Versioned database schema changes
tests/               Flask application tests
instance/            Local database, backups, and bindings (not committed)
config.py
requirements.txt
.python-version      Python 3.13.3 for Render
gunicorn.conf.py     Hosted web server configuration
wsgi.py              Production application entry point
run.py
seed.py
```

The older top-level Jira and synthetic experiment folders have been removed from the active working tree and preserved separately by the project owner. They are not inputs to the current NetEase integration.

## Fresh installation (Windows PowerShell)

Use Python 3.13 (the version used for the verified application run). Clone the branch containing this integration:

```powershell
git clone --branch main https://github.com/Sagooparneet/task-allocation-recommender.git
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
2. Choose **KYC Verification** as the task type.
3. Enter a description and choose a location such as **Nairobi**.
4. Select only **KYC Verification** as the required skill.
5. Choose a deadline on or after today in Kenya time.
6. Save and open recommendations. Workers appear under demonstration aliases linked to their original source IDs.

The required skill selection drives recommendation eligibility; the task title alone does not. The new installation has a local mapping from each original capability label to the same source code. It does not use the legacy KYC demonstration mapping. Website-created tasks are not additional NetEase observations.

### Existing integrated installation

For the original local website, activate the existing environment and run `python run.py`. With no deployment environment variables set, it uses `instance/task_allocation.db` and its matching bindings. Its KYC demonstration mapping remains the fallback when no installation-specific configuration exists.

Some scripts under `scripts/` are legacy migration utilities for the original installation. In particular, `import_netease_agents.py` assumes the original seven-task migration state, and `enable_demo_agent_login.py` targets a verified database/source-ID pair from that migration. Do not run these as the fresh-installation procedure. Use `seed.py` instead.

### Dependencies and deployment boundary

The root `requirements.txt` lists the application and test dependencies with versions verified in the working Python 3.13 environment. It omits unrelated packages from the previous full environment export. A clean online dependency installation has not yet been independently verified.

Research notebook reproduction uses its own isolated environment and `ml/requirements-notebooks.txt`. Its historical NetworkX pin differs from the application environment; do not combine both dependency sets in one environment. Saved artifact inference does not rebuild the graph.

This is an academic prototype with deployment preparation in progress. The original `run.py` enables debug mode, and `config.py` retains a development secret for local use. Public hosting must use `wsgi:app`, which requires explicit production settings and disables debug mode. Public deployment and testing are still pending.

## Deployment preparation: Render and Neon

Neon stores the PostgreSQL database; Render will run the Flask website and saved ML inference. The website is not publicly deployed yet. The local application has been checked against Neon using read-only transactions.

### Database setup (new installations only)

Create an empty Neon PostgreSQL database and install the root requirements in a local virtual environment. Run from the project root:

```powershell
python scripts/check_neon_connection.py
python scripts/check_neon_sqlalchemy.py
python scripts/create_neon_tables.py
python scripts/initialize_neon.py
python scripts/check_neon_application.py
```

Each script prompts privately for the connection string. Initialisation also prompts for a supervisor name, email, and password. Never commit connection strings or passwords.

`create_neon_tables.py` applies the committed initial migration to an empty database. `initialize_neon.py` refuses nonempty application tables and creates one supervisor, 1,653 source-ID worker accounts, four capability skills, and database worker mappings. It creates no tasks or assignments. Worker logins remain disabled. Unknown historical performance remains unknown.

The project owner's Neon database has already completed these steps. Do not rerun schema creation or initialisation against that populated database. Future schema changes require new reviewed migrations; do not reset the database or rerun `db init`.

The existing local databases are separate installations. This process does not transfer their tasks, assignments, accounts, or JSON binding files to Neon.

### Planned Render web service settings

| Setting | Value |
|---|---|
| Service type | Web Service |
| Runtime | Python |
| Region | Frankfurt, matching the Neon region |
| Plan | Free |
| Root directory | Repository root (leave blank) |
| Build command | `python -m pip install -r requirements.txt` |
| Start command | `gunicorn --config gunicorn.conf.py wsgi:app` |
| Python | `3.13.3`, specified in `.python-version` |

Select the branch containing the reviewed deployment changes. During preparation this is `feature/deployment-preparation`; use `main` after those changes have been merged. These settings document the planned deployment, not an already running public service.

Configure these private environment variables in the hosting dashboard:

| Variable | Value |
|---|---|
| `INTELLITASK_DATABASE_URL` | Neon PostgreSQL connection string |
| `INTELLITASK_SECRET_KEY` | A persistent, randomly generated secret of at least 32 characters |

Generate a secret locally with `python -c "import secrets; print(secrets.token_hex(32))"` and store it privately in the hosting settings. Keep it stable across restarts. Do not put it in the README, source files, screenshots, or Git history.

The production entry point selects the Psycopg driver, requires encrypted PostgreSQL connections, and uses database worker bindings. PostgreSQL does not require `INTELLITASK_INSTANCE_PATH` or local JSON mapping files. SQLite production-style tests retain their separate instance-folder configuration.

Gunicorn uses one worker process and a 120-second timeout as an initial configuration. Hosting memory use, startup time, and request performance must still be measured. Gunicorn is installed on Linux; its requirement is skipped on Windows. Use the existing local runners for development.

Do not run setup or initialisation scripts in the build or start command. Database records must survive application restarts. Render's free service filesystem is temporary, so application records belong in Neon; committed ML artifacts are installed again from the repository on deployment. Free services can sleep while inactive and have usage limits. Check current provider terms before relying on them for a demonstration.

Provider documentation: [Render Flask hosting](https://render.com/docs/deploy-flask), [Python version configuration](https://render.com/docs/python-version), [Render free service limits](https://render.com/docs/free), and [Neon plans](https://neon.com/pricing).

### Verification completed on 24 October 2026

- Combined Flask and ML tests: **26 passed**, with 14 SQLAlchemy legacy-API warnings.
- Installed dependency consistency: `python -m pip check` reported no broken requirements. This is not a clean Linux installation test.
- The production workflow check passed task creation, saved-model inference, recommendation display, assignment, duplicate protection, workload changes, and completion using a temporary SQLite copy. The source databases were unchanged.
- The read-only Neon application check verified all 1,653 worker identities, database-backed ML configuration, supervisor login, session-cookie protections, and the authenticated dashboard.
- The Neon check did not create or assign a task. A complete PostgreSQL write workflow and public HTTPS browser test remain pending.
- Worker completion tests simulate an authenticated worker session. Real hosted worker login has not been enabled or verified.

Before declaring the public demo ready, verify the Linux build and model loading, run the task/assignment workflow against the hosted database, review authentication and form protections, and test HTTPS login and session behaviour in a browser. These checks do not establish model accuracy on real onboarding tasks.

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

## Supervisor interface conventions

Names shown for imported workers are synthetic demonstration aliases from the saved display profiles. Original source-worker IDs and database bindings remain unchanged. Aliases do not affect model scores or represent the real identities of NetEase workers.

The interface uses these approved demonstration skill labels:

| Source capability | Display label |
|---|---|
| 50 | SIM Registration |
| 53 | M-PESA Onboarding |
| 56 | KYC Verification |
| 69 | Account Activation |

These labels do not establish real onboarding qualifications or change the meaning of the benchmark. Database skills, submitted skill IDs, ML features, and ranking logic retain their source identities. Historical success rates describe training responses, not real onboarding work; ranking scores are not success probabilities.

Application task locations are Nairobi, Mombasa, Kisumu, Nakuru, and Eldoret. They are operational choices, not worker locations inferred from the dataset. New tasks require a deadline on or after today's date in Kenya time (EAT). Existing tasks without deadlines are retained. These UI changes are being tested locally; they are not yet verified on the public deployment.

## Dashboard theme (issue #46)

The shared IntelliTask theme uses a local SVG logo, stylesheet and small navigation script. No chart service, CDN or additional Python package is required. Task charts use real application counts. The supervisor overview shows only that supervisor's tasks and supports name search, status filters, overdue indicators and ten-row pagination. Deadline comparisons use Kenya time. The worker-history snapshot continues to use the saved source-linked display names and labels described above.

Role navigation only links to existing pages. Google signup, OTP verification, reports, administrator management and the full worker status lifecycle are future work. See [the role feature plan](docs/ROLE_FEATURE_PLAN.md).

The isolated automated check passed 54 tests, with 17 existing SQLAlchemy legacy-method warnings. Desktop/mobile visual review remains pending: the automatic browser preview timed out. These local changes have not yet been verified or published on Render.
