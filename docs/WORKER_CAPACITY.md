# Worker capacity — issue #56

Each worker may receive up to three active assignments across all supervisors. Assigned and In progress both count; Completed does not. Three is an application policy, not a dataset finding. Counts come from actual assignment records rather than the cached workload field.

Existing assignments are never cancelled, rewritten or reassigned by installation. A worker already at or above three keeps their work and must finish enough assignments to fall below three before receiving another. The availability flag remains an independent administrator setting.

Dataset candidates at capacity are excluded before scoring. The ranking algorithm, model weights, source mappings and historical evidence remain unchanged, but the eligible candidate list and ranks may change. Displayed active-task counts use current assignments. The assignment endpoint rechecks capacity under a worker-row write lock and rolls back the pending task claim if full. Completion frees a slot through the existing completion workflow.

The no-op worker UPDATE serializes reservations on PostgreSQL (default READ COMMITTED) and SQLite. Automated checks here exercise SQLite, not hosted PostgreSQL concurrency. The future independent-worker assignment path must use this same policy and reservation pattern; that path is not implemented yet.

No database migration or data backfill is required. Neon and Render remain unchanged. The separate independent-worker registration migration is a different pending step; do not apply it to install capacity controls.
