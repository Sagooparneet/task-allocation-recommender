# Independent-worker registration upgrade — issue #56

Adds one empty independent_worker_registrations table at revision 56c03f1a6b70, following 56b02e0f5a60. Existing workers are not automatically classified as independent. The table records the worker account ID, creating administrator and registration timestamp. It adds no dataset identity or recommendation score.

The fixed port-5001 apply helper requires --apply --server-stopped, checks the local port and database revision, refuses nonempty journals, makes a verified SQLite backup plus three configuration files, rehearses against a temporary backup copy, verifies that source hashes did not change, and then applies the same migration to the fixed local database. All original table columns and records are compared after upgrade; the new table must be empty. Configuration hashes must remain unchanged. A repeated run at the target revision makes no changes.

Stop the server before running the helper. Preserve backups. Failure messages instruct keeping the server stopped and do not automatically downgrade or restore data. Command-line destination is instance/netease_setup_test only; no database URL is accepted. Explicit SQLite configuration prevents selecting Neon through environment variables.

Tests use temporary fixture databases only and cover record/config preservation, repeat application, wrong revision, modified backup and source changes during rehearsal. PostgreSQL deployment is separate work.

This stage prepares storage only. The ORM model, administrator Add Worker form, account provisioning, separate service-matching list and assignment path remain to be implemented. Existing three-task capacity controls remain unchanged.
