# Verified results — 23 October 2026

All six requested notebooks have executed outputs. Six ML/adapter tests passed in 5.29 seconds. The graph figure was visually inspected. These are package tests, not tests of a completed integration into the user's original Flask application.

## Retained dataset

| Split | Tasks | Task-worker observations |
|---|---:|---:|
| Training | 12,473 | 85,647 |
| Validation | 2,018 | 12,316 |
| Test | 2,699 | 17,137 |
| Purged across temporal cutoffs | 797 | 6,101 |
| Total retained sample | 17,987 | 121,201 |

There are 1,653 workers in the candidate catalog. The graph contains only the 1,508 workers with training interactions; the others are cold-start workers. The original three source partitions total 1,203,264 raw rows. Every selected observation was checked against its original source CSV row and source hashes.

## Recomputed results (K=3)

| Model | Top-1 success | Precision@3 | Recall@3 | MAP@3 | Full MAP | NDCG@3 |
|---|---:|---:|---:|---:|---:|---:|
| Preserved legacy hybrid | 80.289% | 79.424% | 62.904% | 74.331% | 84.294% | 79.797% |
| Improved content-only | 69.248% | 69.804% | 56.191% | 62.635% | 77.567% | 69.673% |
| Preserved collaborative-only | 80.289% | 77.572% | 61.487% | 72.579% | 83.178% | 78.309% |
| Genuine KG-only | 80.289% | 77.473% | 61.415% | 72.474% | 83.103% | 78.256% |
| Historical quality-only | 80.511% | 79.573% | 62.962% | 74.511% | 84.423% | 79.970% |
| New genuine-KG hybrid | 79.881% | 77.189% | 61.216% | 72.093% | 82.955% | 77.946% |

These were computed by `src/evaluation.py` from saved training-only features and held-out outcomes. The final notebook checks the legacy Top-1, Precision, Recall and full MAP against the previous report to 1e-12 tolerance. It does not assign the prior reported number as a measured result.

The new hybrid weights are **0.1 content, 0.5 collaborative, 0.4 KG**, selected on validation MAP@3 among 36 positive-weight triples. Its ~79.88% result is distinct from the preserved model's ~80.29%. No subsequent tuning on these test results was performed.

## Evidence of graph contribution

NetworkX graph: 13,985 nodes and 100,154 edges. It contains 85,647 COMPLETED edges, 12,473 REQUIRES_CAPABILITY edges and 2,034 HAS_CAPABILITY edges. Validation, test and purged task nodes are absent.

Removing the KG component and renormalizing the other weights changes the first-ranked candidate on 196 of 2,699 test tasks. The no-KG variant has 80.289% Top-1 and 71.831% MAP@3. Thus adding KG improves MAP@3 modestly against that ablation while reducing Top-1; it does not beat the historical-quality baseline. This is a descriptive result, not a significance or causal claim.

The implementation provides inspectable graph relationships and evidence-based explanations. General robustness and real onboarding effectiveness remain unproven. The test split has been inspected previously, so the new-model comparison is retrospective rather than a new blind evaluation.

See `final_evaluation.json` and `all_metrics.csv` for K=1,3,5 results, Hit@K and confidence intervals. `latency.json` records actual local inference timings. `sample_recommendations.json` contains named demonstration agents with original source IDs and explanations.
