# Explainable NetEase knowledge-graph hybrid

Project: **An Explainable Knowledge Graph-Driven Hybrid Recommender for Intelligent Task Allocation in Distributed Onboarding Operations.**

## Inspection of the previous work

The prior NetEase system already had valid source hashes, task-worker provenance, answer-equals-truth outcomes, deterministic task sampling, chronological task-level splits, boundary purging, training-only history fitting, a reusable JSON inference engine, executed notebooks and a measured ~80% Top-1 result. These remain intact.

The current dataset is `data/netease/observations.csv`, with `split_task_ids.json` and `provenance.json`. It has 121,201 observations, 17,987 tasks and 1,653 source workers. Original partitions 1, 6 and 11 remain under `data/raw/netease/` (1,203,264 raw rows). This delivery retains the complete usable existing experiment, not all public NetEase data. Expanding the sample would change the experiment and should be evaluated separately.

The preserved trained files are `models/netease/legacy_model.json` and `legacy_evaluation.json`. The old result comes from choosing the first-ranked **observed participant** on each of 2,699 held-out tasks and checking the source answer against ground truth. The final notebook recomputes it from features and labels.

The previous ML graph-context score was **not** a genuine knowledge graph: it was `.55*quality + .45*free_capacity`. Its explanation paths were generated strings, not traversals of a NetworkX graph. With neutral source context it reduced to quality ranking. The old content score was constant. Both deficiencies are documented; the preserved model is a baseline, not retroactively described as a KG-trained model.

Your original Flask `app/services/recommendation_service.py` separately builds a NetworkX graph from application records. It currently computes recommendations for your database agents using fixed component weights. It does not load the NetEase model. In a later manual stage, its public service interface can remain while an adapter delegates ranking to this ML package. No current Flask file is modified here.

## Structure

```text
ml/
  data/netease/                   # unchanged processed observations and split/provenance
  data/raw/netease/               # unchanged source CSVs, license and manifest
  notebooks/
    01_netease_data_preparation.ipynb
    02_content_based_filtering.ipynb
    03_collaborative_filtering.ipynb
    04_knowledge_graph.ipynb
    05_hybrid_recommender.ipynb
    06_final_evaluation.ipynb
  models/netease/
    legacy_model.json             # old trained model, unchanged
    legacy_evaluation.json        # old reference result, unchanged
    hybrid.json                   # new weights selected on validation MAP@3
    knowledge_graph.json          # saved NetworkX training graph
    features.json                 # compiled features and graph evidence for inference
    capability_profiles.json
    display_profiles.json         # explicit source/display mapping + provenance
    task_index.json               # source membership and capability, NO outcome labels
  salesmesh_ml/                   # original reusable implementation, retained
  src/
    preprocessing.py
    content_based.py
    collaborative.py
    knowledge_graph.py
    hybrid.py
    evaluation.py
    explainability.py
    display_profiles.py
    recommender.py
    flask_adapter.py              # optional pure adapter for a later manual stage
  reports/                       # newly computed metrics, figures and sample explanations
  tests/
```

## Model methodology

**Content:** cosine compatibility between log-transformed training participation counts by capability and task requirements. No synthetic skills or test success labels enter these profiles. Participation is evidence of experience, not verified professional competence.

**Collaborative:** preserve the old neighbor-smoothed worker/category correctness score. Its neutral capability profiles give equal neighbor similarities. It is not SVD or a neural model. This component is reused, not rewritten under a new name.

**Knowledge graph:** a NetworkX DiGraph includes Worker, Task and Capability nodes. COMPLETED edges carry training outcomes; REQUIRES_CAPABILITY edges connect tasks to capabilities; HAS_CAPABILITY edges summarize observed training participation. Shared-worker-task paths identify co-participation neighbors. A 60% smoothed own capability outcome / 40% graph-neighbor capability prior score is computed from those graph relationships. Node/edge statistics, graph visualization, path evidence and validation evaluation are shown in notebook 04. Removing graph paths/evidence changes features; tests verify this.

**Hybrid:** validation MAP@3 selects nonnegative 0.1-step weights with at least 0.1 for each component. This architectural constraint was fixed before the new test evaluation to ensure CBF, CF and actual KG all contribute. It does not guarantee higher accuracy. The legacy unconstrained model remains unchanged for comparison. Final results include content-only, collaborative-only, KG-only, quality-only, legacy hybrid and the new KG hybrid, plus a no-KG ablation. We report any worse outcomes honestly.

All graph construction and historical profiles use training outcomes only. The source worker/catalog membership includes cold-start workers for replay, but not their future outcomes. The fixed test benchmark was seen during earlier project work; evaluation of the new architecture is therefore retrospective. A genuinely new holdout is needed for a fresh generalization claim.

## Source IDs and demonstration identities

Every profile retains the exact raw `source_worker_id`, e.g. `10000`, plus a stable display identifier such as `AGENT_0001` and a human-readable name. IDs are strings; do not cast source task IDs to floating point.

> Agent names are synthetic display identities used for demonstration and privacy. The underlying historical interactions originate from the NetEaseCrowd dataset.

Historical task count, success rate and capability participation are derived from **training** observations. Experience labels summarize recorded count, not real employment tenure. Names, Kenyan locations and initial availability/workload/capacity are demonstration fields with explicit provenance. None affects benchmark scores. No credentials, emails or real-world identity claims are manufactured.

## Inference boundary

```python
from ml.src.recommender import recommend_agents
```

The function loads saved artifacts once per process. It performs no retraining, Flask imports, database writes or graph rebuilding. The graph's computed features and evidence are compiled into the model artifacts; the full saved graph remains available for auditing. Restart the application after intentionally changing artifacts.

Benchmark mode requires a held-out `source_task_id` and uses that task's observed candidate set. Application-demo mode instead requires explicit source `capability_ids` and explicitly mapped `candidate_worker_ids`. It is deliberately labeled separate from benchmark inference. Multiple capability scores are equally averaged in demo mode.

No automatic semantic mapping from KYC, M-PESA or SIM registration to a numeric NetEase capability is assumed. The future host adapter must receive an explicitly documented demonstration mapping. This is a proxy demonstration, not evidence that the model learned KYC expertise.

Optional live/demo operations can filter unavailable/full candidates and blend 10% free capacity with 90% ML ranking in application-demo mode only. Benchmark mode rejects operational overrides. Display-profile default workload/availability are not automatically used to rank workers.

## Mapping to the existing Flask database — design, not applied changes

Use an external mapping from Flask `OnboardingAgent.id` to exact NetEase `source_worker_id`. Do not equate these integers or treat `AGENT_0001` as a database primary key. The mapping represents a demonstration profile association, not a real identity match.

The supplied pure `src/flask_adapter.py` can accept already-loaded Task/agent objects, explicit identity bindings and an explicit task-type/capability mapping. It checks the existing task's required skill names against the candidate's application skills and availability before inference, and maps recommendations back to the existing database agent IDs. It neither inserts agents nor rewrites SQLAlchemy models. Synthetic names are display labels; the underlying original account and authorization checks remain the host application's responsibility.

At the manual service stage, `get_recommendations(task_id, limit=5)` can keep its existing public signature. At the template stage, ranking scores must be labeled as scores, historical success rates with no data handled as unknown, and weights/explanations updated. The old threshold text cannot be assumed valid for new scores. At the assignment stage, the existing route must recheck authorization, eligibility and duplicate assignment constraints; a ranked source worker alone is not a valid SQLAlchemy assignment target.

Do not call or copy the adapter into active service code until the earlier manual stages have passed. Authentication, dashboards, routes and database schemas remain unchanged at this delivery stage.

## Academic interpretation

* Dataset: real public NetEaseCrowd observations.
* Evaluation: observed-participant task replay on retained temporal splits.
* Application domain: distributed onboarding operations, demonstrated using a proxy because industry assignment data was unavailable.
* Identity/context: synthetic display identity and separately documented application state.

Suitable wording: “The legacy hybrid recommender achieved approximately 80% Top-1 success on held-out NetEaseCrowd task-worker observations used as a proxy for intelligent task allocation.” Report the new genuine-KG hybrid’s result separately, using the generated report. Neither number is Kenyan onboarding accuracy.

Explanations and auditable graph paths are implemented properties. Better robustness, causal allocation benefit or better onboarding performance have not been established merely by adding a graph. An inferior baseline comparison must not be hidden.

## Notebook execution and tests

Saved notebook outputs are immediately viewable. For reproduction, use Python 3.12 and an isolated environment while opening the folder containing `ml`:

```powershell
python -m pip install -r ml/requirements-notebooks.txt
```

Select that interpreter as the notebook kernel and run notebooks 01–06 in order. To execute via script, register your chosen environment's python3 kernel, then run `python ml/run_notebooks.py`. The script supports `--start 4` for resuming after a display-only fix; artifact changes require rerunning dependent stages.

Independent package tests: install pytest in the chosen environment, then run `python -m pytest ml/tests -q` from the folder containing `ml`. These are ML/adapter tests; they are not claims that the unmodified user's Flask application has been integrated or tested.

Preserve the original dataset license/citation at `data/raw/netease/`. Official source: https://github.com/fuxiAIlab/NetEaseCrowd-Dataset . No synthetic outcomes have replaced the source dataset.
