# Task titles and services needed

Create Task now uses a required free-text Task title (maximum 100 characters), Task instructions, and Services needed. The services remain the existing skill checkboxes with their original database IDs. At least one service is required; the title does not infer or replace a requirement.

No database migration or data rewrite is needed. The title is stored in the existing Task.task_type field. Existing TaskSkill links, worker identities, capability mappings and ML artifacts are unchanged. Older submissions using task_type=__other__ and custom_task_type continue to be accepted for compatibility.

The active HybridRecommendationService delegates to NetEaseRecommendationService. Its ranking input uses explicit selected capabilities and eligible worker IDs. The task title is returned as display metadata, not passed as a ranking feature. This statement concerns the active NetEase route; unused legacy scoring code is unchanged.

Verification compares ranked worker IDs, source IDs, scores and component scores for two different task titles with the same service IDs. It also checks required and overlong titles, preserved form entries, unchanged existing tasks, and older form submissions.

Manual check: create a clearly named job such as Register new customers at KICC, select the services it requires, then choose its venue, reporting point and deadline. Review recommendations and confirm the selected services are shown. Existing tasks should still appear with their saved names.
