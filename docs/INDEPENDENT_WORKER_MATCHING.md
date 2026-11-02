# Independent worker matching

The supervisor recommendations page has a separate "New workers matching this task" section. It lists administrator-added workers alphabetically, ten per page. These are service matches, not ML-ranked recommendations. No prediction, ranking score or historical success rate is invented.

A worker must have an independent registration, a completed account setup, an enabled account, availability on, all selected service IDs confirmed by an administrator, fewer than three actual active assignments and no source dataset binding. Empty or unsupported task requirements produce no matches. Service links match the exact registered service IDs. City is shown for the supervisor to check reporting arrangements; it does not filter or rank workers.

The separate POST action requires a supervisor who owns the task and a valid assignment CSRF token. It rechecks eligibility rather than trusting hidden form fields. A conditional task update prevents duplicate allocation. The existing worker lock and active-assignment count enforce the three-task limit across supervisors. Registration, services and source identity are checked again after locking. Assignment, task status and workload commit together.

Assigned work appears in the worker dashboard and uses the existing start and complete actions. Completion creates application task history only. It does not turn the worker into a NetEase identity, change ML weights or automatically retrain the model.

Existing model results retain their scoring and order. Independent matching can remain available during a model loading error because it does not use model scores. Invalid source-binding configuration fails closed for independent matches.

## Local verification

On port 5001, complete the new worker's password setup and enable availability in their administrator profile. Sign in as the supervisor and open a pending task requiring services registered for that worker. Find the separate section below Suggested workers. Assign, then sign in as the worker to start and complete the task. Repeat submission must not duplicate assignments. Workers with three active tasks must disappear until a slot becomes free.

The automated tests cover matching, permissions, CSRF, stale forms, source identity protection, separate assignment routes, unchanged model results, transaction rollback, capacity, pagination and the worker progress workflow. SQLite concurrency is checked locally; hosted PostgreSQL validation remains separate. No schema change or Neon migration is part of this stage.

## Email invitations

Initial account invitations support private manual sharing or Gmail API email delivery using the same expiring single-use invitation. Local Gmail authorization is encrypted outside the repository and loaded by the email-enabled launcher. Hosted secrets and the public invitation origin remain deployment work. See [Gmail API invitations](GMAIL_API_INVITATIONS.md). Neither delivery method changes matching rules or creates dataset history.
