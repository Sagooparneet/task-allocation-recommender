# IntelliTask

**An Explainable Knowledge Graph-Driven Hybrid Recommender for Intelligent Task Allocation in Distributed Onboarding Operations.**

IntelliTask is a Flask prototype in which supervisors create tasks, review recommendations, and assign workers. The worker workflow supports viewing assignments, starting work and marking in-progress tasks complete after worker login has been explicitly enabled. Fresh dataset accounts have login disabled. Recommendations use saved models built from real NetEaseCrowd observations.

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
  -> worker starts the assignment (In progress; start time recorded)
  -> worker completes it (Completed; finish time recorded; workload reduced once)
```

The active hybrid uses **10% content, 50% collaborative, and 40% knowledge graph**. It loads saved artifacts rather than retraining during page requests. Knowledge-graph features and explanation evidence are precomputed from the saved training graph.

The service checks source-worker bindings, recorded capabilities, and website availability. The assignment route checks task ownership, the form token, current eligibility, and duplicate assignment conditions. Actual active workload is capped at three assignments for new allocations; it is not a component of the active website ranking score. Completing a website task does not automatically retrain the model.

Administrator-added independent workers use a separate service-matching list and never receive invented dataset scores or histories.

Worker history and recommendation evidence come from saved training records. Dashboard task counts come from application records; neither is a new measure of model accuracy.

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
- Imported workers are displayed using demonstration aliases linked to their original source IDs. These are not source identities or model evidence. Legacy account locations are not verified worker service areas.
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
tests/               Flask application tests and frontend JavaScript tests
instance/            Local database, backups, and bindings (not committed)
config.py
requirements.txt
.python-version      Python 3.13.3 for Render
gunicorn.conf.py     Hosted web server configuration
wsgi.py              Production application entry point
run.py
seed.py
```

The older top-level Jira and synthetic experiment folders are not inputs to the current NetEase integration.

## Account bootstrap for a fresh installation (Windows PowerShell)

Use Python 3.13 (the version used for the verified application run). Clone the branch containing this integration:

```powershell
git clone --branch main https://github.com/Sagooparneet/task-allocation-recommender.git
cd task-allocation-recommender
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed.py --instance-dir instance/netease_setup_test --check-only
python seed.py --instance-dir instance/netease_setup_test
```

The setup prompts for a supervisor name, email, and password of at least 12 characters. Password input is hidden and only its hash is stored. Open `http://127.0.0.1:5001/auth/login` and use that account. The supervisor name/email are user-provided application account information, not NetEase attributes.

This bootstrap is not yet an end-to-end venue-enabled installation procedure: `seed.py` creates tables from the current models but does not record migration history, provision an administrator or seed the venue directory. Review schema and migration history and provision venues before creating tasks; do not blindly stamp an existing database. The verified port-5001 installation described below has already completed its controlled upgrade.

Setup creates 1,653 worker accounts labelled by original source ID, four capability skills, and one supervisor. It creates no tasks or assignments and no administrator account. Workers without training history have an unknown success rate. Source profiles have no invented locations or personal names. Worker logins are disabled until explicitly configured for a local demonstration.

The destination folder must not exist. Setup refuses to overwrite an existing installation. If interrupted, preserve the partial folder for inspection and use a new destination only after investigating the error. Do not delete or reset your working database to rerun setup.

The runner uses `instance/netease_setup_test` explicitly, a separate session cookie, port 5001, and debug disabled. Its random session secret changes on restart, requiring users to sign in again. Do not reuse a binding file with a different database. `setup_complete.json` marks successful initialisation.

### Current port-5001 installation and task workflow

The existing `instance/netease_setup_test` installation has been backed up and upgraded through migration `66c09f702b34` (Google identities), including email verification, password recovery, supervisor invitations, worker invitations, task progress and work venues. It has the five initial venues and a separately provisioned administrator. Start the normal local website with:

```powershell
python run_netease_test.py
```

1. Sign in as supervisor and choose **Create Task**.
2. Enter a **Task title**, such as “Register new customers”, and task instructions.
3. Select one or more **Services needed**. These retain the original skill IDs and drive recommendation eligibility.
4. Select a city and an active work location. Check the address preview and enter the confirmed reporting point. Arrival instructions and contact details are optional.
5. Choose a priority and a required deadline on or after today in Kenya time.
6. Save, inspect Location details, open recommendations and assign a worker.
7. A worker with an explicitly enabled local login can view the saved address and reporting point, choose **Start task**, then **Mark complete** when finished.
8. Refresh the supervisor dashboard to see updated totals, task status and recorded start/completion times.

The title remains in the existing `tasks.task_type` column. Changing its wording does not alter the active NetEase ranking inputs. The form does not infer services from the title. Existing tasks and skill links are not rewritten.

The installation-specific mapping links original capability labels to source codes. It does not rely on the older KYC-only fallback configuration. Website-created tasks and venue details are application records, not additional NetEase observations.

### Task progress tracking (issue #54)

The local workflow is **Assigned → In progress → Completed**. Starting work keeps the worker's active workload unchanged. Completing it reduces workload once, with a floor of zero. Only the assigned worker can submit either action, and both actions require a valid session form token. Task and assignment status changes are committed together; completion also records the finish time and updates workload in that transaction. Repeated or stale requests do not overwrite timestamps or reduce workload again. Completion requires an in-progress assignment with a recorded start time.

The nullable `task_assignments.started_at` and `completed_at` columns store UTC timestamps without timezone offsets. Pages display these in Kenya time (EAT, UTC+3). Existing `assigned_at` values and deadline conventions are unchanged. Historical tasks retain their original statuses and records; unknown historical start/completion times stay empty and are not invented. These two timestamps are not a full event/audit history.

The supervisor dashboard separates Waiting, Assigned (not started), In progress and Completed in its totals, chart and filters. Totals cover all tasks owned by the signed-in supervisor even when the table is filtered. Recorded start and completion times appear beside task statuses. Worker counts include both assigned and in-progress work as active. Refresh the page after another user updates a task; live push updates are not implemented.

The port-5001 upgrade has already been applied and verified. Its controlled helpers are:

- `scripts/check_task_progress_schema.py`: test migration, preservation and downgrade protection using a new disposable SQLite database.
- `scripts/backup_5001_before_task_progress.py`: create a verified backup of the fixed local installation and matching configuration files.
- `scripts/check_5001_task_progress_upgrade.py --backup <verified-backup-folder>`: rehearse the upgrade on a temporary copy and compare existing records.
- `scripts/apply_5001_task_progress_upgrade.py --apply --server-stopped`: with port 5001 stopped, make a fresh backup, rehearse, then apply and verify the fixed local upgrade.

Do not rerun upgrade helpers as routine startup steps or use them against Neon. Preserve backups. The migration refuses a downgrade that would discard recorded progress timestamps. Fresh installations and the original `run.py` database need their own schema review; the port-5001 upgrade does not upgrade other installations.

No model features, source bindings, ranking weights or recommendation scores are changed by task-progress tracking. Website progress is application activity, not additional NetEase training evidence. Neon and Render remain unchanged by issue #54.

### Work location management (issue #49)

Administrators can list and filter locations by city/status, add or edit venues, and deactivate/reactivate them. Multiple venues can be stored in each of the five cities. The initial directory contains KICC in Nairobi, PrideInn Nyali in Mombasa, Acacia Premier Hotel in Kisumu, Merica Hotel in Nakuru, and Boma Inn Eldoret in Eldoret. See [venue sources and migration notes](docs/WORK_VENUES.md).

New tasks require an active venue belonging to the selected city. The backend saves the task, service links and location snapshot together. Supervisor task lists, recommendations and assigned-agent views show the saved details. Venue edits never rewrite those snapshots; older city-only tasks keep their original location without a guessed venue.

Venue management is administrator-only and writes require form tokens. Task creation also checks its form token, title, selected services, location and deadline. Location is not a new ML feature or evidence of a worker's travel eligibility.

The controlled local helpers are `backup_5001_before_venues.py`, `check_5001_venue_upgrade.py`, `apply_5001_venue_upgrade.py` and `setup_local_admin_login.py`. They target the port-5001 installation and are not general Neon migration tools. The upgrade and administrator setup have already run for this installation; do not rerun them as routine startup steps.

Further details: [task location integration](docs/TASK_WORK_LOCATIONS.md), [task titles and services](docs/TASK_TITLES_AND_SERVICES.md).

### Existing integrated installation

For the original local website, activate the existing environment and run `python run.py`. With no deployment environment variables set, it uses `instance/task_allocation.db` and its matching bindings. Its KYC demonstration mapping remains the fallback when no installation-specific configuration exists.

Some scripts under `scripts/` are legacy migration utilities for the original installation. In particular, `import_netease_agents.py` assumes the original seven-task migration state, and `enable_demo_agent_login.py` targets a verified database/source-ID pair from that migration. Do not run these as the fresh-installation procedure. Use `seed.py` instead.

### Dependencies and deployment boundary

The root `requirements.txt` lists the application and test dependencies with versions verified in the working Python 3.13 environment. It omits unrelated packages from the previous full environment export. A clean online dependency installation has not yet been independently verified.

Research notebook reproduction uses its own isolated environment and `ml/requirements-notebooks.txt`. Its historical NetworkX pin differs from the application environment; do not combine both dependency sets in one environment. Saved artifact inference does not rebuild the graph.

This is an academic prototype with deployment preparation in progress. The original `run.py` enables debug mode, and `config.py` retains a development secret for local use. Public hosting must use `wsgi:app`, which requires explicit production settings and disables debug mode. An earlier version was deployed to Render and its supervisor dashboard was opened successfully. The current local venue, interface and task-progress changes have not yet been verified on that hosted version.

## Deployment preparation: Render and Neon

Neon stores the PostgreSQL database; Render hosts the Flask website and saved ML inference. An earlier deployment reached the login page and supervisor dashboard successfully. The checks below describe that earlier setup; this issue does not update Neon or Render. Before deploying the current code, apply and verify the venue, task-progress and worker-management migrations and directory setup on PostgreSQL separately. Current code requires the progress timestamps, profile_display_name and account_disabled columns; the local upgrade helpers must not be used against Neon.

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

If Neon already contains the initial workers and supervisor, skip schema creation and initialisation. For later changes, apply reviewed migrations to that database; do not reset it or rerun `db init`.

The existing local databases are separate installations. This process does not transfer their tasks, assignments, accounts, or JSON binding files to Neon.

### Render web service settings

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

Select the branch containing the reviewed deployment changes. During preparation this is `feature/deployment-preparation`; use `main` after those changes have been merged. The last recorded hosted branch was `feature/deployment-preparation`. Pushing a feature branch does not itself switch that service to the new branch. Confirm the configured Render branch before changing deployment settings.

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

### Before deploying the current code

1. Back up Neon and apply the versioned migrations that are missing from its current revision. Rehearse the PostgreSQL upgrade on a disposable copy first. Do not run the port-5001 SQLite upgrade helpers against Neon.
2. Configure Render with the production variables below, a stable secret key, and a public HTTPS URL. Register that URL as the Google sign-in callback.
3. Configure hosted email delivery separately. The Windows-protected local Gmail authorization file cannot be used by Render.
4. Test HTTPS sign-in, first-time setup, password reset, Google sign-in, task creation, recommendations, assignment, worker start/completion and supervisor totals against the hosted database.
5. Check the Linux build, saved-model loading, memory use and session-cookie protections before demonstrating the public site.

The earlier hosted deployment reached the login page and supervisor dashboard. Treat the full hosted workflow as unverified until the steps above pass. Website task outcomes do not establish model accuracy on real onboarding work.

## Research notebooks

The six notebooks are under `ml/notebooks/`:

1. `01_netease_data_preparation.ipynb`
2. `02_content_based_filtering.ipynb`
3. `03_collaborative_filtering.ipynb`
4. `04_knowledge_graph.ipynb`
5. `05_hybrid_recommender.ipynb`
6. `06_final_evaluation.ipynb`

Saved outputs can be viewed without executing them. Reproduction instructions and notebook dependencies are included in the ML package. Run notebooks in numerical order in an isolated research environment; executing them can regenerate model artifacts and reports.

## Tests

From the project root, run:

```powershell
python -m pytest tests ml/tests -q
node --test tests/js/accessibility_preferences.test.cjs tests/js/deadline_calendar.test.cjs tests/js/worker_setup.test.cjs
python -m pip check
```

The latest full local check passed **433 Python tests** and **16 JavaScript tests**. The Python run reported 120 SQLAlchemy and Flask-SQLAlchemy deprecation warnings. Tests use disposable databases; they do not verify the public website or Neon. Run the hosted workflow checks above before deploying new changes. Node.js is needed for the JavaScript tests, not for running Flask.

## Supervisor reports (issue #60)

Supervisors can open **Reports** from their navigation to review their own tasks. The page reads application records; it does not run model inference or measure recommendation accuracy.

- Totals show all tasks, waiting, assigned, in progress, completed and overdue. Overdue means unfinished work with a recorded deadline before the current Kenya time; it overlaps the status totals.
- Optional **Created from** and **Created through** filters include both complete recorded calendar dates. Both fields allow today or earlier in Kenya time, with matching server validation and linked error messages. Blank dates show all tasks. Task deadlines still allow future dates.
- Interactive doughnut charts show task progress and priority in responsive Bootstrap cards. The charts are custom SVG, not a Bootstrap chart plugin. Visible labels, counts, percentages and keyboard-accessible links provide equivalent information and selection without relying on colour or JavaScript.
- Selecting a slice or label filters the task table to that category. Charts and headline totals keep showing the whole selected date period. **Show all tasks** clears the category while retaining dates; pagination preserves both dates and category.
- The table shows task title, recorded assigned worker names, status and deadline, with ten tasks per page. Empty results, missing assignments/deadlines and older unknown status/priority values are handled explicitly.

All report queries are restricted to the signed-in supervisor. Records and dataset mappings are unchanged. No migration, new dependency, external chart service or email action is required.

Creation filters use the existing recorded `created_at` calendar dates. These legacy timestamps are timezone-naive server-local values; the report does not infer or rewrite historical timezone offsets. Statuses reflect the current state, not historical snapshots. Review timestamp consistency when deploying to PostgreSQL.

### Check reports

Sign in as a supervisor, open **Reports**, and check the totals, date filters, chart drill-down and task table against that supervisor's tasks. Future creation dates should be rejected; task deadlines may still be in the future. Then run:

```powershell
python -m pytest tests/test_supervisor_reports.py tests/test_dashboard_overview.py tests/test_supervisor_progress.py tests/test_role_theme.py -q
```

See [report behavior and checks](docs/SUPERVISOR_REPORTS.md). CSV/PDF exports and historical trend reports are outside issue #60.

## Supervisor interface conventions

Names shown for imported workers default to synthetic demonstration aliases from the saved display profiles. Administrators may override the displayed name without replacing the original source identity. Original source-worker IDs and database bindings remain unchanged. Aliases do not affect model scores or represent the real identities of NetEase workers.

The interface uses these approved demonstration skill labels:

| Source capability | Display label |
|---|---|
| 50 | SIM Registration |
| 53 | M-PESA Onboarding |
| 56 | KYC Verification |
| 69 | Account Activation |

These labels do not establish real onboarding qualifications or change the meaning of the benchmark. Database skills, submitted skill IDs, ML features, and ranking logic retain their source identities. Historical success rates describe training responses, not real onboarding work; ranking scores are not success probabilities.

Application task cities are Nairobi, Mombasa, Kisumu, Nakuru, and Eldoret, with administrator-managed work venues within each city. They are operational choices, not worker locations inferred from the dataset. New tasks require a deadline on or after today's date in Kenya time (EAT). Existing tasks without deadlines are retained. These UI changes are being tested locally; they are not yet verified on the public deployment.

## Dashboard theme (issue #46)

The shared IntelliTask theme uses a local SVG logo, stylesheet and small navigation script. No chart service, CDN or additional Python package is required. Task charts use real application counts. The supervisor overview shows only that supervisor's tasks and supports name search, status filters, overdue indicators and ten-row pagination. Deadline comparisons use Kenya time. Worker names and service labels retain their source bindings as described above.

Role navigation links to implemented pages, including administrator work locations and supervisor management. The agent dashboard supports task filtering, deadline sorting, details and the Assigned → In progress → Completed workflow. Supervisor reports are implemented locally. First-time email verification, password recovery and Google sign-in are implemented locally under issue #66. See [the role feature plan](docs/ROLE_FEATURE_PLAN.md).

Check the supervisor and worker dashboards and the administrator locations page in the local browser after changing shared styles. Deploy current local changes only after completing the hosted checklist above.


## Accessibility and role colours (issue #52)

The shared interface uses teal for supervisors, blue for workers and purple for administrators. Portal labels identify roles in text; task status labels retain their meaning independently of role colours.

A Settings button on the login page and each role portal provides:

- Light, Dark and System default appearance.
- Normal, Large, Extra large and Huge text.
- High contrast, Bold text and Reduce motion options.
- Reset preferences to restore defaults.

Preferences apply immediately and are saved in the current browser. They are not synchronised between accounts or devices. System default follows the device appearance, and device reduced-motion preferences remain respected. If browser storage is unavailable, settings apply to the current page and a message explains they could not be saved.

Keyboard navigation includes visible focus indicators, a skip-to-content link, a mobile navigation toggle and a settings dialog that returns focus to its opener when closed. The settings controls support keyboard operation and include accessible names.

Create Task, login and administrator Add/Edit work location forms provide error summaries linked to the affected fields. Invalid fields have associated error messages, and focus moves to the summary after an unsuccessful submission. Entered details remain available for correction; login passwords are always cleared and never returned in HTML. Incorrect credentials use a general message for both known and unknown accounts. Server validation remains active with JavaScript disabled; automatic focus handling requires JavaScript.

Task creation refreshes the selected venue record before validation so an outdated cached active flag does not bypass the inactive-location check. Recommendation inputs, dataset bindings and existing task snapshots are unchanged by these interface improvements.

Check saved preferences, form-error links, retained entries, keyboard navigation, dark mode and enlarged text on port 5001. Include a screen-reader review and wider mobile/browser coverage before claiming accessibility conformance. The local settings do not update Neon or Render.

Further details: [settings and appearance](docs/SETTINGS_AND_APPEARANCE.md), [Create Task errors](docs/ACCESSIBLE_TASK_FORM.md), and [login and location form errors](docs/LOGIN_LOCATION_ERRORS.md).


## Administrator worker management — issue #56

Implemented and checked on the local port-5001 installation:

- Worker listing, search, availability filters, pagination, profiles, services and assignment history.
- Editing display names while preserving original dataset identities and source bindings.
- Availability controls for new assignments, and account deactivation/reactivation with administrator-only access, form tokens and confirmation. Deactivation refuses unfinished or inconsistent assignments; reactivation leaves availability off.
- A maximum of **three actual active assignments** (Assigned or In progress) per worker. Eligibility and assignment-time checks enforce capacity without deleting existing assignments. Workload is an eligibility constraint, not a new ML scoring feature.
- Administrator-created independent workers with validated, unique email addresses and administrator-confirmed services. They receive their own registration records, with no borrowed dataset identity, history or model score.
- Expiring, single-use initial password invitations for pending independent workers. The database stores the token hash; successful redemption sets a hashed password and enables login while leaving availability off until an administrator enables it. Reissuing replaces the previous invitation. This is not password recovery for existing accounts.
- A separate **New workers matching this task** list. Eligible independent workers must match all required service IDs and are listed alphabetically, not ranked by the NetEase model. Supervisors retain the assignment decision. Assignment, start, completion and workload updates use the existing protected workflow.
- Gmail API email invitations, with manual sharing still available. The recipient comes from the worker record, and emailed links use a configured origin. Email reissues have a one-minute guard. Failed or uncertain submission preserves the new link for manual sharing and does not report successful delivery.

Dataset-backed recommendation weights and historical evidence remain unchanged. Availability, disabled-account and capacity checks can change which workers are eligible. Completing website tasks does not retrain the model or turn an independent worker into a dataset worker.

### Editing independent worker services — issue #64

An administrator can open **Workers → an independently added worker → Edit services** and choose from the configured service labels. The form requires at least one service, an administrator confirmation and a valid form token. It rejects stale changes and refuses dataset-backed worker identities. A source worker's observed capabilities remain read-only.

The saved selection changes **future** matches in the separate new-worker list. Previously assigned tasks and their statuses remain in place, including when a service is removed. The edit does not change source bindings, training records, model scores or the service catalogue. Legacy and current skill rows with the same displayed service label are kept together so tasks using either row can match. No database migration or model retraining is needed for this feature. The administrator should review a worker's services before making them available for new assignments.

### Local Gmail use

The sending account is authorized with the Gmail sending-only scope. OAuth credentials are saved outside the project using Windows-user DPAPI encryption. They are never stored in the application database or committed to Git. Gmail authorization is separate from Google sign-in for website users, and sending an invitation does not set an email-verification flag.

After completing the authorization helper, start the existing local installation with:

```powershell
python scripts/run_5001_with_gmail_api.py
```

This loads the saved authorization and enables email submission from the administrator's invitation form. The ordinary `python run_netease_test.py` launcher supports manual sharing but does not load the Gmail connection. No email is sent automatically on startup. Local emailed links must be opened on the computer running the website.

See [local authorization](docs/GMAIL_LOCAL_AUTHORIZATION.md), [email invitations](docs/GMAIL_API_INVITATIONS.md), [password setup](docs/WORKER_PASSWORD_SETUP.md), [independent matching](docs/INDEPENDENT_WORKER_MATCHING.md) and [worker capacity](docs/WORKER_CAPACITY.md).

### Check worker management

Use the administrator portal to create an independent worker, choose services, send or privately share a setup invitation, and keep availability off until the account is ready. After password setup, enable availability and assign a matching task. Sign in as that worker to start and complete it, then refresh the supervisor dashboard to confirm the totals. Run the full test commands in [Tests](#tests).

Keep verified local database backups. The local upgrade helpers are installation-specific and are not routine startup commands. Neon and Render require their own migration and hosted email checks before receiving these features. The Windows encrypted Gmail credential file is not a Render credential. Self-service account edits and service-catalogue management remain separate work.

## Administrator supervisor management — issue #62

On the local port-5001 installation, administrators can list and search supervisors, edit their names, and deactivate or reactivate accounts. Deactivation refuses supervisors with unfinished tasks and preserves their account, task and assignment records. New supervisors are registered with a name and unique email address; they cannot sign in until they complete initial password setup. Existing supervisors are not asked to reset their passwords.

For a pending supervisor, the administrator can create a one-time setup invitation and choose **Email to [registered address]** or private manual sharing. The invitation expires after 24 hours; the database stores its hash, not the plain setup code. Issuing a replacement invalidates the previous link. The supervisor enters their registered email and chooses a password of 12–128 characters. Successful setup enables their supervisor sign-in. This is initial setup, not password recovery or public self-registration.

Email uses the existing Gmail sender configuration and fixed invitation website address. On port 5001, start with `python scripts/run_5001_with_gmail_api.py` to enable Gmail delivery. `python run_netease_test.py` supports manual sharing only. The email option sends only when the administrator selects it and confirms the invitation. Repeated email requests within one minute are refused. If Gmail submission cannot be confirmed, the new link remains available for manual sharing and the page does not claim successful delivery. Localhost links must be opened on the computer running the website.

For a new installation, apply migrations `62a05b3c8d90` and `62b06c4d9e01` before using supervisor management. Back up and rehearse upgrades on an existing database. To check the workflow, add a supervisor, send a setup invitation, complete password setup, sign in, and test deactivation/reactivation. These actions do not change NetEase worker mappings, training evidence, recommendation scoring or task history.

Neon and Render have not been upgraded for issue #62. The local port-5001 backup and upgrade scripts are installation-specific and must not be run against Neon. Hosted rollout requires separate PostgreSQL migration and verification, a public HTTPS invitation address, and hosted Gmail authorization. The Windows encrypted Gmail credential file is not available to Render.


## Bootstrap frontend integration (issue #57)

The frontend uses **Bootstrap 5.3.8 with Flask-rendered Jinja2 templates**, alongside IntelliTask's custom theme. Bootstrap supplies layout and interface components; Flask handles routes, validation and permissions, SQLAlchemy handles application data, and the existing Python recommendation services provide rankings.

Bootstrap assets are pinned and served locally from `app/static/vendor/bootstrap-5.3.8/`, including the MIT licence, grid CSS, JavaScript bundle, selective Sass source and compiled component CSS. Browsers do not need a CDN connection for these assets. The manifest records SHA-256 hashes. Flask runs with the committed assets; Node.js and Sass are only needed for frontend tests or rebuilding CSS.

The frontend includes:

- Responsive dashboard grids, buttons, text inputs, selects, cards and tables.
- Status badges and pagination that retain existing labels, filters and links.
- Shared navigation styling and labelled feedback messages; messages do not disappear on a timer.
- A compact worker search/filter toolbar that wraps on smaller screens.
- Normal body and shared control text now use .9375rem (normally 15px); smaller secondary text stays at .875rem (normally 14px). Saved accessibility choices still apply.
- A custom deadline calendar with month navigation, keyboard controls and a separate time field. This is an IntelliTask component, not a Bootstrap calendar plugin. It preserves the original required date/time field as a fallback, submits the existing Kenya civil-time format and rejects dates before today. Backend validation still applies.

The selective Bootstrap build includes forms, buttons, cards, tables, badges, pagination, navigation and alerts. Full Reboot, Bootstrap progress bars and replacement modal styles are not loaded, avoiding conflicts with existing charts and dialogs. Existing mobile navigation, Settings and calendar scripts retain control of their own interactions. There are no duplicate Bootstrap collapse or modal controllers.

Teal supervisor, blue worker and purple administrator themes remain in place. Accessibility styles load last, retaining appearance preferences, enlarged text, high contrast, reduced motion, keyboard focus and accessible form errors. Check these behaviors across supported browsers and with assistive technology before claiming accessibility conformance.

These frontend changes do not require a database migration or alter source-worker mappings, recommendation features or ranking weights. Deploy the current frontend only after the hosted database is compatible with the current application code.

### Maintain the frontend

Run the commands in [Tests](#tests) after changing Bootstrap assets or shared styles. Keep build folders and `node_modules` out of commits. Preserve the vendor licence, Sass source, generated CSS and matching manifest together. Check the dashboard, forms, calendar and accessibility settings at normal and enlarged text sizes in a browser.

See [the integration overview](docs/BOOTSTRAP_INTEGRATION.md), [forms and build instructions](docs/BOOTSTRAP_CONTROLS.md), [cards and tables](docs/BOOTSTRAP_CARDS_TABLES.md), [status and pagination](docs/BOOTSTRAP_STATUS_PAGINATION.md), [deadline calendar](docs/DEADLINE_CALENDAR.md), and [navigation and messages](docs/BOOTSTRAP_NAVIGATION_MESSAGES.md).

## Account sign-in and recovery (issue #66)

To sign in, enter the email and password for an existing administrator, supervisor or worker account. Use the eye button to show or hide the password. The compact desktop form can scroll when larger accessibility text is selected. For a newly invited supervisor or independent worker, open the setup link, request the six-digit code sent to the registered email, enter it within ten minutes, and then choose a first password. Existing accounts keep their passwords. Administrators control account creation.

To recover an account, choose **Forgot password**, enter its registered email and follow the link sent to that address within 30 minutes. The request page gives the same response for known and unknown addresses. Reset links are single-use, stored as hashes, and subject to request limits. Changing a password invalidates prior login sessions and attempts to send a confirmation email. Local delivery requires the Gmail sender connection.

To use **Continue with Google**, first have an approved, active IntelliTask account with the same verified Gmail or Google Workspace address. Google sign-in uses a separate OAuth Web application client with `openid email` only. It does not create accounts, enable disabled accounts, accept pending invitations or grant dataset workers login access. Password sign-in remains available. This client does not request Gmail sending permission.

For port 5001, configure a separate Google Web client with the exact authorized callback `http://127.0.0.1:5001/auth/google/callback`. Keep its downloaded JSON outside the repository. In the PowerShell terminal used to start the local website:

```powershell
$env:INTELLITASK_GOOGLE_SIGNIN_CLIENT_FILE = "C:\path\outside\project\sign-in-client.json"
$env:INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI = "http://127.0.0.1:5001/auth/google/callback"
python scripts/run_5001_with_gmail_api.py
```

The Google button appears only when the client is configured. If Google's authorization screen is in Testing mode, add the chosen Google account as an allowed test user. Its email must match an existing active IntelliTask account. Keep the client JSON and Gmail sender credentials outside the repository and out of documentation.

For a new installation, apply migrations `66a07d5e0f12` (first-time email verification), `66b08e6f1a23` (password reset) and `66c09f702b34` (Google identity) before using these flows. Back up and rehearse upgrades for an existing database. The port-5001 installation already has these migrations; do not rerun its upgrade helpers on startup. These features do not change NetEase source bindings or recommendation scoring.

Run the commands in [Tests](#tests) after changing authentication code. Check password sign-in, first-time email verification, password reset and Google sign-in in the local browser. The login form supports a compact desktop layout and saved accessibility text sizes. These local checks do not verify hosted authentication or database compatibility.

Neon and Render have **not** received these migrations or the current authentication code. Hosted rollout requires a separate reviewed PostgreSQL upgrade, a public HTTPS Google callback registered with Google, private hosting variables `INTELLITASK_GOOGLE_SIGNIN_CLIENT_ID`, `INTELLITASK_GOOGLE_SIGNIN_CLIENT_SECRET` and `INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI`, and hosted email-delivery credentials. The local Windows-protected Gmail authorization is not available on Render. Do not run the port-5001 migration helpers against Neon.
