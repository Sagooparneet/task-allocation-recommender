# Worker setup invitation storage upgrade — issue #56

The fixed local port-5001 upgrade moves from 56c03f1a6b70 to 56d04a2b7c80, adding one empty worker_setup_invitations table. All original tables and records are compared before/after, including pending independent registrations, worker password hashes and source bindings. No credentials are enabled or changed by this migration.

Stop port 5001 before running scripts/apply_5001_worker_setup_upgrade.py --apply --server-stopped. It verifies the expected starting revision, refuses active local server/journal state, creates a verified SQLite backup and copies three configuration files, rehearses the upgrade on a temporary copy, checks source hashes remain unchanged, applies to the fixed local installation and verifies preservation. It accepts no external database URL. A repeat run at the target schema makes no changes.

Keep the printed backup. On failure, keep the server stopped and retain the backup; the helper does not automatically restore or downgrade. Neon and Render are not accessed. PostgreSQL verification is separate work.

The four automated helper tests use disposable fixture installations only. They check successful preservation and repeat application, wrong revision refusal, backup tampering refusal and source changes during rehearsal. The invitation schema checker separately validates hash, identity, expiry and downgrade constraints.

This is storage preparation only. Invitation issuance, secure delivery, one-time redemption, password hashing and the setup interface still need implementation. Existing users and dataset-linked accounts retain their credentials. Pending independent workers remain disabled and unavailable until their explicit setup flow is implemented and completed.
