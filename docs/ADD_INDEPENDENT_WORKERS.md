# Administrator Add Worker — issue #56

Requires the local registration migration 56c03f1a6b70. The ORM model matches that table. This stage adds the administrator-only /admin/workers/new form, linked from the worker directory.

Administrators enter a name, their worker's own email, a base city and one or more existing supported services, and confirm they have checked those services. This is administrator confirmation, not an automated qualification assessment. Emails are normalized to lowercase and checked across all existing account roles. No verification email is sent in this stage. Invalid values use linked accessible errors and retained entries.

The transaction creates a new OnboardingAgent, service links labelled Administrator confirmed, and an IndependentWorkerRegistration recording its creating administrator and timestamp. Source binding tables and files are never written. A proposed account ID must not overlap an existing binding. Missing or malformed file-mode identity configuration refuses creation and rolls back the account. Additional posted role, score, password, availability and source-ID fields are ignored.

A new account starts disabled and unavailable, with zero workload, NULL performance_score and an unusable password marker. No dataset identity, history, model score or success rate is invented. The profile says Awaiting account setup and No recorded performance history. Ordinary reactivation cannot bypass initial setup. Duplicate submits cannot create a second account with the same email.

Remaining work: secure initial account setup, the separately labelled service-matching list, and its protected assignment path using the three-active-task policy. Existing dataset ranking remains based on existing bindings; new registrations are not model candidates. Later website completions must not be represented as automatically retraining the model or proving quality.

Local check: administrator -> Workers -> Add worker. Submit an empty form to check errors, then register a person with their own details and confirmed services. Their profile should show the pending setup state and no assignments. Search by email to find them. Existing workers and their account controls must continue working.

These records are application registrations, not NetEase dataset observations. Neon and Render are unchanged; deployment and account email verification remain separate work.
