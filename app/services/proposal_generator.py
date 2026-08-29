"""ProposalGenerator: builds a short, personalized proposal.

V1 uses a deterministic template (no AI cost, fully testable). The output
structure mirrors what a real LLM would return, so V2 can optionally route
this through the AIProvider interface without changing the API contract.

Note: proposals are only *prepared* — Fix50 Agent never sends anything
automatically (no messaging, no payments).
"""
from __future__ import annotations

from app.models import Analysis, OpportunityInput, Proposal, ScoreResult

_MIN_PRICE = 50.0


class ProposalGenerator:
    """Generates a Proposal for opportunities scoring >= 70."""

    def generate(
        self,
        opportunity: OpportunityInput,
        analysis: Analysis,
        score: ScoreResult,
    ) -> Proposal:
        suggested_price = self._suggested_price(analysis)
        problem_summary = analysis.problem
        solution = self._proposed_solution(analysis)
        return Proposal(
            problem_summary=problem_summary,
            proposed_solution=solution,
            delivery_estimate=analysis.estimated_time,
            suggested_price=suggested_price,
            message=self._build_message(
                opportunity, problem_summary, solution,
                analysis.estimated_time, suggested_price,
            ),
        )

    @staticmethod
    def _suggested_price(analysis: Analysis) -> float:
        midpoint = (analysis.price_min + analysis.price_max) / 2
        rounded = round(midpoint / 25.0) * 25.0
        return max(rounded, _MIN_PRICE)

    @staticmethod
    def _proposed_solution(analysis: Analysis) -> str:
        skills = ", ".join(analysis.required_skills[:3]) or "a pragmatic approach"
        return (
            f"I would handle this end to end using my skills in {skills}. "
            f"Given the scope ({analysis.difficulty.value} difficulty), I'd start "
            f"with a quick diagnosis, apply a focused fix, and verify it works "
            f"before handover."
        )

    @staticmethod
    def _build_message(
        opportunity: OpportunityInput,
        problem: str,
        solution: str,
        delivery: str,
        price: float,
    ) -> str:
        client = opportunity.client_name or "there"
        return (
            f"Hi {client},\n"
            f"\n"
            f'Thanks for posting "{opportunity.title}".\n'
            f"\n"
            f"Here is what I understood: {problem}\n"
            f"\n"
            f"Proposed solution: {solution}\n"
            f"\n"
            f"Timeline: I can deliver within {delivery}.\n"
            f"Price: fixed price of ${price:.0f}.\n"
            f"\n"
            f"Happy to answer any questions or get started right away.\n"
            f"\n"
            f"Best regards"
        )
