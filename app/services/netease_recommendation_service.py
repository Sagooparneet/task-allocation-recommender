from app.services.recommendation_presentation import worker_summary
from app.services.worker_display_names import worker_display_name

import json
from pathlib import Path

from flask import current_app
from app.extensions import db
from app.models import OnboardingAgent, Task, AgentSkill, Skill, WorkerSourceBinding
from ml.src.recommender import load_artifacts, recommend_agents


class NetEaseRecommendationService:
    def _read_configuration(self):
        storage = current_app.config.get("NETEASE_BINDING_STORAGE", "file")
        if storage not in ("file", "database"):
            raise ValueError("Unknown NetEase binding storage mode.")

        if storage == "database":
            rows = WorkerSourceBinding.query.all()
            if not rows:
                raise ValueError("No NetEase worker mappings found in the database.")
            workers = {str(row.agent_id): row.source_worker_id for row in rows}
            if len(set(workers.values())) != len(workers):
                raise ValueError("Duplicate NetEase source-worker bindings detected.")
            artifacts = load_artifacts()
            if not set(workers.values()).issubset(artifacts["profiles"]):
                raise ValueError("Database worker mappings do not match the saved model.")
            capability_map = {
                f"NetEase capability {code}": [code]
                for code in artifacts["model"]["capabilities"]
            }
            return workers, capability_map

        project = Path(current_app.root_path).parent
        mapping_path = Path(current_app.instance_path) / 'netease_agent_bindings.json'
        # Use installation-specific configuration when available.
        capability_path = (
            Path(current_app.instance_path)
            / "onboarding_capability_mapping.json"
        )

        # Preserve the configuration used by the existing website.
        if not capability_path.is_file():
            capability_path = (
                project
                / "ml/config/onboarding_capability_mapping.json"
            )
        bindings = json.loads(mapping_path.read_text(encoding='utf-8-sig'))
        config = json.loads(capability_path.read_text(encoding='utf-8-sig'))
        if bindings.get('schema_version') != 1 or bindings.get('status') != 'ready':
            raise ValueError('NetEase agent import mapping is not ready.')
        workers = bindings.get('worker_bindings')
        if not isinstance(workers, dict) or not workers:
            raise ValueError('No database-to-source-worker bindings found.')
        if len(set(workers.values())) != len(workers):
            raise ValueError('Duplicate source-worker bindings detected.')
        if config.get('schema_version') != 1 or not isinstance(config.get('skill_to_capabilities'), dict):
            raise ValueError('Invalid onboarding capability configuration.')
        return workers, config['skill_to_capabilities']

    def get_eligible_candidates(self, task_id):
        """Return task, required source capabilities and source-ID -> DB agent map.

        Host routes must enforce supervisor authorization before calling this.
        This function can also support assignment-time eligibility rechecks later.
        """
        task = db.session.get(Task, task_id)
        if task is None:
            raise ValueError(f'Task {task_id} does not exist.')
        bindings, capability_map = self._read_configuration()
        artifacts = load_artifacts()
        known = set(artifacts['model']['capabilities'])
        required_skills = sorted({link.skill.name for link in task.task_skills})
        if not required_skills:
            raise ValueError('Task has no required skills; add explicit requirements before recommending.')
        capabilities = set()
        for skill in required_skills:
            mapped = capability_map.get(skill)
            if not isinstance(mapped, list) or not mapped or any(c not in known for c in mapped):
                raise ValueError(f'No valid demonstration capability mapping for required skill: {skill}')
            capabilities.update(mapped)
        expected_labels = {'NetEase capability ' + c for c in capabilities}
        skills_by_agent = {}
        for agent_id, skill_name in db.session.query(AgentSkill.agent_id, Skill.name).join(
            Skill, Skill.id == AgentSkill.skill_id
        ).all():
            skills_by_agent.setdefault(agent_id, set()).add(skill_name)

        candidates = {}
        for agent in OnboardingAgent.query.filter_by(availability=True).all():
            source_id = bindings.get(str(agent.id))
            if source_id is None:
                continue
            profile = artifacts['profiles'].get(source_id)
            if profile is None or agent.email != f'netease-{source_id}@demo.invalid':
                raise ValueError(f'Identity mapping mismatch for database agent {agent.id}.')
            # All required skills must be mapped and supported; never choose only
            # the first skill or invent KYC qualifications for a source worker.
            if not expected_labels.issubset(set(profile['skills'])):
                continue
            if not expected_labels.issubset(skills_by_agent.get(agent.id, set())):
                continue
            candidates[source_id] = agent
        return task, sorted(capabilities), candidates

    def get_recommendations(self, task_id, limit=5):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be an integer between 1 and 100.')
        task, capabilities, candidates = self.get_eligible_candidates(task_id)
        if not candidates:
            return []
        ranked = recommend_agents({
            'mode': 'application_demo',
            'capability_ids': capabilities,
            'candidate_worker_ids': list(candidates),
        }, top_k=limit)
        artifacts = load_artifacts()
        weights = artifacts['model']['weights']
        results = []
        for row in ranked:
            agent = candidates[row['source_worker_id']]
            rate = row['historical_success_rate']
            reasons = [
                'Demonstration mapping: ' + ', '.join(sorted({s.skill.name for s in task.task_skills}))
                + ' -> NetEase capabilities ' + ', '.join(capabilities)
                + '; this is not evidence of real onboarding qualifications.',
                *row['explanation'],
            ]
            results.append({
                **row,
                'agent_display_id': row['agent_id'],
                'agent_id': agent.id,  # Existing assignment endpoint expects the DB primary key.
                'agent_name': worker_display_name(row['source_worker_id']),
                'task_id': task.id,
                'task_type': task.task_type,
                'match_percentage': round(row['score'] * 100, 2),
                'cbf_score': row['components']['content'],
                'cf_score': row['components']['collaborative'],
                'kg_score': row['components']['knowledge_graph'],
                'decision': 'Supervisor review required',
                'availability': agent.availability,
                'workload': agent.workload,
                'performance_score': None if rate is None else rate * 100,
                'explanation': ' '.join(reasons),
                'explanations': reasons,
                'model_weights': weights,
                'workload_used_in_score': False,
                'summary': worker_summary(artifacts['features'][row['source_worker_id']], capabilities),
            })
        return results
