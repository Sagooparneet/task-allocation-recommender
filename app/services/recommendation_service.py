from abc import ABC, abstractmethod

from app.models import OnboardingAgent, Task


class RecommendationService(ABC):

    @abstractmethod
    def get_recommendations(self, task_id, limit=3):
        pass


class MockRecommendationService(RecommendationService):

    def get_recommendations(self, task_id, limit=3):

        task = Task.query.get(task_id)

        if not task:
            return []

        available_agents = (
            OnboardingAgent.query
            .filter_by(availability=True)
            .limit(limit)
            .all()
        )

        mock_scores = [0.90, 0.85, 0.80]

        recommendations = []

        for index, agent in enumerate(available_agents):

            score = (
                mock_scores[index]
                if index < len(mock_scores)
                else 0.75
            )

            recommendations.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "task_id": task.id,
                "task_type": task.task_type,
                "score": score,
                "explanation": (
                    "Mock recommendation for system development. "
                    "The real hybrid recommender has not yet been implemented."
                )
            })

        return recommendations