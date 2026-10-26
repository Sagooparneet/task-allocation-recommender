# Work venues — issue #49

## Initial directory

These real venues are proposed examples for scheduled onboarding sessions. Listing a venue does not establish an affiliation, booking or authorisation to provide financial/telecom services there. Venue and room arrangements must be confirmed before real operations. No room numbers, staff contacts or worker travel abilities are inferred.

| City | Venue | Published location | Source |
| --- | --- | --- | --- |
| Nairobi | Kenyatta International Convention Centre (KICC) | Harambee Avenue, Nairobi CBD | https://kicc.co.ke/ |
| Mombasa | PrideInn Nyali | Links Road area, behind City Mall, Nyali | https://www.prideinn.co.ke/hotels-in-mombasa/prideinn-nyali/ |
| Kisumu | Acacia Premier Hotel | Achieng' Oneko Road, Kisumu | https://acaciapremier.com/contact-us/ |
| Nakuru | Merica Hotel | Kenyatta Avenue, Nakuru | https://merica.co.ke/conference-centre/ |
| Eldoret | Boma Inn Eldoret | Elgon View Drive, off Ramogi Drive | https://www.theboma.co.ke/inn-eldoret/ |

The venue directory is operational application data, not part of NetEase training data. It does not affect ML ranking or establish an agent's service area. Published addresses should be reconfirmed for actual bookings; specific reporting points are supplied per task.

## Schema

- `work_venues`: editable directory, with city, name, address, optional directions/map URL and active status. Several venues can exist in the same city. An optional stable setup key prevents repeat setup from overwriting administrator changes.
- `task_venue_details`: one saved location record per task, containing the venue ID plus copies of the name, city, address, directions and map link, together with reporting point, instructions and optional contact details. Directory edits do not refresh these copies.
- Existing tasks keep `tasks.location` and have no `task_venue_details` record. No venue is guessed for historical tasks.
- Foreign keys restrict removal of referenced records. The UI deactivates venues instead of deleting them.

Migration `49a01b7c2d30` follows `4baace48147a` and adds only two tables and their indexes. It does not alter existing task columns or insert venue rows. Its downgrade deletes the new tables, including their data, so rollback is tested only in the disposable database at this stage.

## Implemented locally

The port-5001 database was backed up, rehearsed in a disposable copy, and upgraded to revision `49a01b7c2d30`. The five initial venues were seeded. Existing accounts, tasks, assignments and recommendation scores were checked for preservation.

Administrator routes support listing, filtering, creation, editing and active/inactive status, with role and form-token checks. Task creation validates an active venue in the selected city and saves its snapshot in the same transaction as the task and selected services. Supervisor and assigned-agent screens show those saved details. Legacy city-only tasks have no inferred venue.

Run `python scripts/check_venue_schema.py` for an isolated migration, history-preservation and rollback check. Rollback in a live database would remove the venue tables and their data; it is not a routine cleanup step.

`add_initial_venues(session)` is repeat-safe for a single setup operator and preserves existing administrator edits. The controlled port-5001 upgrade helper calls it after schema verification. Do not blindly stamp older `create_all()` databases or rerun installation scripts against populated Neon tables.

## Release boundary

The task workflow is documented in [TASK_WORK_LOCATIONS.md](TASK_WORK_LOCATIONS.md). Finish the manual task/assignment/agent-view walkthrough, then review PostgreSQL migration and deployment separately. The existing Neon database and Render deployment were not changed by this local feature work. SQLite checks alone do not prove the hosted PostgreSQL upgrade.

Map URLs are validated as HTTPS when edited by the administrator and are retained in task snapshots. The current task detail panel shows text directions, address and contact details; it does not expose a map-link button.

Issue #48 still needs the separate In Progress workflow. No ML features or location-based eligibility rules were added.
