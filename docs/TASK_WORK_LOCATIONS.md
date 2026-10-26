# Task work locations (issue #49)

Prerequisite: venue migration 49a01b7c2d30 is already applied to the selected database. This change needs no further schema migration. Do not deploy this code to a database without the venue tables.

Supervisors select a city and an active venue, then enter a required reporting point (desk, entrance or room). The form previews the stored address and directions. Arrival instructions and contact details are optional. JavaScript filters the venue choices by city; the server independently validates city, active status, reporting point and field lengths. Without JavaScript, all active venues are listed with their city and server validation still applies. An empty venue list directs the supervisor to the administrator.

The server reads venue details from the database, ignoring any browser-submitted address. It saves Task, TaskSkill and TaskVenueDetails together in one transaction. Task creation also requires a session form token. Failure rolls back all task writes. Existing deadline, city and skill checks remain; unknown skill IDs and invalid priority values are rejected.

Supervisor task lists and recommendations, and the assigned agent's task details, display the saved venue, address, reporting point, directions, arrival instructions and contact details. Queries are limited to the current user's tasks or assignments. Old tasks without a snapshot keep their original city; they are not assigned a venue automatically. Editing or deactivating a venue does not rewrite past task snapshots.

These locations are application scheduling data. They do not establish a real worker's location or modify the NetEase model inputs, skill mappings, recommendation scores or training data. The previously documented real venues are demonstration event locations, not claims of affiliation or authorised onboarding operations.

The production workflow checker now supplies a venue, reporting point and form token. It extends only its disposable database copy with any missing tables and initial venues; it is not a substitute for testing live migrations. Neon is not changed by these local checks.

Validation: python -m pytest tests ml/tests -q. Additional manual checks: select different cities, inspect the address preview, save a task with a confirmed reporting point, view its location details, assign it, and inspect the assigned agent's task details. Use an administrator to deactivate a venue and verify it disappears from new-task choices while old task details remain unchanged.
