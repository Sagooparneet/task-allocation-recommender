from abc import ABC, abstractmethod
from collections import defaultdict
from math import sqrt

import networkx as nx

from app.models import (
    OnboardingAgent,
    Task,
    AgentSkill,
    TaskSkill,
    TaskAssignment
)


class RecommendationService(ABC):

    @abstractmethod
    def get_recommendations(self, task_id, limit=5):
        pass


class HybridRecommendationService(RecommendationService):

    HYBRID_WEIGHTS = {
        "cbf": 0.30,
        "cf": 0.30,
        "kg": 0.40
    }

    CBF_WEIGHTS = {
        "skill": 0.50,
        "specialization": 0.20,
        "location": 0.10,
        "performance": 0.10,
        "workload": 0.10
    }

    KG_WEIGHTS = {
        "skill_relation": 0.50,
        "location_relation": 0.15,
        "historical_task_type": 0.20,
        "performance": 0.15
    }

    MINIMUM_SUITABILITY_SCORE = 0.60

    PROFICIENCY = {
        "Beginner": 1,
        "Intermediate": 2,
        "Advanced": 3
    }

    def get_recommendations(self, task_id, limit=5):

        task = Task.query.get(task_id)

        if not task:
            return []

        available_agents = (
            OnboardingAgent.query
            .filter_by(availability=True)
            .all()
        )

        if not available_agents:
            return []

        all_agents = OnboardingAgent.query.all()

        max_workload = max(
            (agent.workload or 0 for agent in all_agents),
            default=0
        )

        # ----------------------------------------
        # Task required skills
        # ----------------------------------------

        task_skill_rows = (
            TaskSkill.query
            .filter_by(task_id=task.id)
            .all()
        )

        task_skill_ids = {
            row.skill_id
            for row in task_skill_rows
        }

        # ----------------------------------------
        # Agent skills
        # ----------------------------------------

        agent_skill_rows = AgentSkill.query.all()

        agent_skills = defaultdict(dict)

        for row in agent_skill_rows:

            agent_skills[row.agent_id][
                row.skill_id
            ] = self.PROFICIENCY.get(
                row.proficiency_level,
                1
            )

        # ----------------------------------------
        # Completed assignment history
        # ----------------------------------------

        completed_assignments = (
            TaskAssignment.query
            .filter_by(status="Completed")
            .all()
        )

        cf_data = self._build_cf_data(
            all_agents,
            completed_assignments
        )

        graph = self._build_knowledge_graph(
            all_agents,
            agent_skill_rows,
            completed_assignments
        )

        recommendations = []

        for agent in available_agents:

            cbf_result = self._calculate_cbf(
                agent=agent,
                task=task,
                task_skill_ids=task_skill_ids,
                agent_skills=agent_skills,
                max_workload=max_workload
            )

            cf_result = self._calculate_cf(
                agent=agent,
                task=task,
                cf_data=cf_data
            )

            kg_result = self._calculate_kg(
                agent=agent,
                task=task,
                graph=graph,
                task_skill_ids=task_skill_ids,
                agent_skills=agent_skills
            )

            hybrid_score = (
                self.HYBRID_WEIGHTS["cbf"]
                * cbf_result["score"]

                + self.HYBRID_WEIGHTS["cf"]
                * cf_result["score"]

                + self.HYBRID_WEIGHTS["kg"]
                * kg_result["score"]
            )

            decision = (
                "Suitable"
                if hybrid_score
                >= self.MINIMUM_SUITABILITY_SCORE
                else "Supervisor review required"
            )

            explanation = self._generate_explanation(
                cbf_result,
                cf_result,
                kg_result
            )

            recommendations.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "task_id": task.id,
                "task_type": task.task_type,

                "score": round(
                    hybrid_score,
                    4
                ),

                "match_percentage": round(
                    hybrid_score * 100,
                    1
                ),

                "cbf_score": round(
                    cbf_result["score"],
                    4
                ),

                "cf_score": round(
                    cf_result["score"],
                    4
                ),

                "kg_score": round(
                    kg_result["score"],
                    4
                ),

                "decision": decision,

                "explanation": explanation,

                "availability":
                    agent.availability,

                "workload":
                    agent.workload,

                "performance_score":
                    agent.performance_score
            })

        recommendations.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return recommendations[:limit]

    # ==========================================
    # CONTENT-BASED FILTERING
    # ==========================================

    def _calculate_cbf(
        self,
        agent,
        task,
        task_skill_ids,
        agent_skills,
        max_workload
    ):

        skill_scores = []

        for skill_id in task_skill_ids:

            level = agent_skills[
                agent.id
            ].get(
                skill_id,
                0
            )

            skill_scores.append(
                level / 3.0
            )

        if skill_scores:
            skill_match = (
                sum(skill_scores)
                / len(skill_scores)
            )
        else:
            skill_match = 0.0

        specialization_match = (
            1.0
            if self._same_text(
                agent.specialization,
                task.task_type
            )
            else 0.0
        )

        location_match = (
            1.0
            if self._same_text(
                agent.location,
                task.location
            )
            else 0.0
        )

        performance_score = self._clamp(
            (agent.performance_score or 0)
            / 100.0
        )

        if max_workload > 0:

            workload_score = self._clamp(
                1.0
                - (
                    (agent.workload or 0)
                    / max_workload
                )
            )

        else:
            workload_score = 1.0

        score = (
            self.CBF_WEIGHTS["skill"]
            * skill_match

            + self.CBF_WEIGHTS[
                "specialization"
            ]
            * specialization_match

            + self.CBF_WEIGHTS["location"]
            * location_match

            + self.CBF_WEIGHTS[
                "performance"
            ]
            * performance_score

            + self.CBF_WEIGHTS["workload"]
            * workload_score
        )

        return {
            "score": self._clamp(score),
            "skill_match": skill_match,
            "specialization_match":
                specialization_match,
            "location_match":
                location_match,
            "performance":
                performance_score,
            "workload_score":
                workload_score
        }

    # ==========================================
    # COLLABORATIVE FILTERING
    # ==========================================

    def _build_cf_data(
        self,
        agents,
        completed_assignments
    ):

        interactions = defaultdict(
            lambda: defaultdict(float)
        )

        task_types = set()

        for assignment in completed_assignments:

            if not assignment.task:
                continue

            task_type = (
                assignment.task.task_type
            )

            task_types.add(task_type)

            interactions[
                assignment.agent_id
            ][task_type] += 1.0

        return {
            "agents": agents,
            "interactions": interactions,
            "task_types": sorted(task_types)
        }

    def _calculate_cf(
        self,
        agent,
        task,
        cf_data
    ):

        interactions = (
            cf_data["interactions"]
        )

        task_types = (
            cf_data["task_types"]
        )

        # Not enough history for CF yet.
        # A neutral score prevents invented evidence.
        if (
            not task_types
            or task.task_type
            not in task_types
        ):
            return {
                "score": 0.50,
                "neighbors_used": 0,
                "used_fallback": True
            }

        target_vector = interactions[
            agent.id
        ]

        if not target_vector:
            return {
                "score": 0.50,
                "neighbors_used": 0,
                "used_fallback": True
            }

        neighbors = []

        for other_agent in cf_data["agents"]:

            if other_agent.id == agent.id:
                continue

            other_vector = interactions[
                other_agent.id
            ]

            if not other_vector:
                continue

            similarity = (
                self._cosine_similarity(
                    target_vector,
                    other_vector,
                    task_types
                )
            )

            target_type_count = (
                other_vector.get(
                    task.task_type,
                    0.0
                )
            )

            if (
                similarity > 0
                and target_type_count > 0
            ):

                neighbors.append(
                    (
                        similarity,
                        target_type_count
                    )
                )

        neighbors.sort(
            key=lambda item: item[0],
            reverse=True
        )

        neighbors = neighbors[:10]

        if not neighbors:
            return {
                "score": 0.50,
                "neighbors_used": 0,
                "used_fallback": True
            }

        max_count = max(
            count
            for _, count in neighbors
        )

        weighted_total = 0.0
        similarity_total = 0.0

        for similarity, count in neighbors:

            normalized_count = (
                count / max_count
                if max_count > 0
                else 0.0
            )

            weighted_total += (
                similarity
                * normalized_count
            )

            similarity_total += similarity

        score = (
            weighted_total
            / similarity_total
            if similarity_total > 0
            else 0.50
        )

        return {
            "score": self._clamp(score),
            "neighbors_used":
                len(neighbors),
            "used_fallback": False
        }

    # ==========================================
    # KNOWLEDGE GRAPH
    # ==========================================

    def _build_knowledge_graph(
        self,
        agents,
        agent_skill_rows,
        completed_assignments
    ):

        graph = nx.DiGraph()

        tasks = Task.query.all()
        task_skill_rows = TaskSkill.query.all()

        for agent in agents:

            graph.add_node(
                f"agent:{agent.id}",
                node_type="Agent",
                performance_score=(
                    agent.performance_score
                    or 0.0
                )
            )

            if agent.location:

                graph.add_node(
                    f"location:{agent.location}",
                    node_type="Location"
                )

                graph.add_edge(
                    f"agent:{agent.id}",
                    f"location:{agent.location}",
                    relation="LOCATED_IN"
                )

        for task in tasks:

            graph.add_node(
                f"task:{task.id}",
                node_type="Task",
                task_type=task.task_type
            )

            if task.location:

                graph.add_node(
                    f"location:{task.location}",
                    node_type="Location"
                )

                graph.add_edge(
                    f"task:{task.id}",
                    f"location:{task.location}",
                    relation="LOCATED_IN"
                )

        for row in agent_skill_rows:

            skill_node = (
                f"skill:{row.skill_id}"
            )

            graph.add_node(
                skill_node,
                node_type="Skill"
            )

            graph.add_edge(
                f"agent:{row.agent_id}",
                skill_node,
                relation="HAS_SKILL",
                proficiency_level=(
                    row.proficiency_level
                )
            )

        for row in task_skill_rows:

            skill_node = (
                f"skill:{row.skill_id}"
            )

            graph.add_node(
                skill_node,
                node_type="Skill"
            )

            graph.add_edge(
                f"task:{row.task_id}",
                skill_node,
                relation="REQUIRES_SKILL"
            )

        for assignment in completed_assignments:

            graph.add_edge(
                f"agent:{assignment.agent_id}",
                f"task:{assignment.task_id}",
                relation="COMPLETED_TASK"
            )

        return graph

    def _calculate_kg(
        self,
        agent,
        task,
        graph,
        task_skill_ids,
        agent_skills
    ):

        agent_node = (
            f"agent:{agent.id}"
        )

        task_node = (
            f"task:{task.id}"
        )

        skill_scores = []

        for skill_id in task_skill_ids:

            level = agent_skills[
                agent.id
            ].get(
                skill_id,
                0
            )

            skill_scores.append(
                level / 3.0
            )

        skill_relation_score = (
            sum(skill_scores)
            / len(skill_scores)
            if skill_scores
            else 0.0
        )

        agent_locations = {
            node
            for node in graph.successors(
                agent_node
            )
            if graph[
                agent_node
            ][node].get("relation")
            == "LOCATED_IN"
        }

        task_locations = {
            node
            for node in graph.successors(
                task_node
            )
            if graph[
                task_node
            ][node].get("relation")
            == "LOCATED_IN"
        }

        location_relation_score = (
            1.0
            if agent_locations
            & task_locations
            else 0.0
        )

        same_type_history = False

        for node in graph.successors(
            agent_node
        ):

            edge = graph[
                agent_node
            ][node]

            if (
                edge.get("relation")
                != "COMPLETED_TASK"
            ):
                continue

            historical_task_type = (
                graph.nodes[
                    node
                ].get("task_type")
            )

            if self._same_text(
                historical_task_type,
                task.task_type
            ):
                same_type_history = True
                break

        historical_task_type_score = (
            1.0
            if same_type_history
            else 0.0
        )

        performance_score = self._clamp(
            (agent.performance_score or 0)
            / 100.0
        )

        score = (
            self.KG_WEIGHTS[
                "skill_relation"
            ]
            * skill_relation_score

            + self.KG_WEIGHTS[
                "location_relation"
            ]
            * location_relation_score

            + self.KG_WEIGHTS[
                "historical_task_type"
            ]
            * historical_task_type_score

            + self.KG_WEIGHTS[
                "performance"
            ]
            * performance_score
        )

        return {
            "score": self._clamp(score),

            "skill_relation_score":
                skill_relation_score,

            "location_relation_score":
                location_relation_score,

            "historical_task_type_score":
                historical_task_type_score,

            "performance":
                performance_score
        }

    # ==========================================
    # EXPLAINABILITY
    # ==========================================

    def _generate_explanation(
        self,
        cbf,
        cf,
        kg
    ):

        reasons = []

        if cbf["skill_match"] >= 0.80:
            reasons.append(
                "strong match with the task's required skills"
            )

        elif cbf["skill_match"] >= 0.50:
            reasons.append(
                "matches several of the required skills"
            )

        if cbf["specialization_match"] == 1.0:
            reasons.append(
                "specialization matches the task type"
            )

        if cbf["location_match"] == 1.0:
            reasons.append(
                "located in the same service area"
            )

        if cbf["workload_score"] >= 0.60:
            reasons.append(
                "has a manageable current workload"
            )

        if cbf["performance"] >= 0.75:
            reasons.append(
                "has a strong performance score"
            )

        if (
            not cf["used_fallback"]
            and cf["score"] >= 0.60
        ):
            reasons.append(
                "has positive collaborative history from similar agents"
            )

        if (
            kg[
                "historical_task_type_score"
            ]
            == 1.0
        ):
            reasons.append(
                "has previously completed the same type of task"
            )

        if not reasons:
            return (
                "Limited supporting evidence is available. "
                "Supervisor review is recommended."
            )

        return "; ".join(reasons) + "."

    # ==========================================
    # HELPERS
    # ==========================================

    @staticmethod
    def _same_text(first, second):

        return (
            str(first or "")
            .strip()
            .lower()
            ==
            str(second or "")
            .strip()
            .lower()
        )

    @staticmethod
    def _clamp(value):

        return max(
            0.0,
            min(
                float(value),
                1.0
            )
        )

    @staticmethod
    def _cosine_similarity(
        first,
        second,
        dimensions
    ):

        dot_product = sum(
            first.get(item, 0.0)
            * second.get(item, 0.0)
            for item in dimensions
        )

        first_norm = sqrt(
            sum(
                first.get(item, 0.0) ** 2
                for item in dimensions
            )
        )

        second_norm = sqrt(
            sum(
                second.get(item, 0.0) ** 2
                for item in dimensions
            )
        )

        if (
            first_norm == 0
            or second_norm == 0
        ):
            return 0.0

        return (
            dot_product
            / (
                first_norm
                * second_norm
            )
        )