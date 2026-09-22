"""Greedy maximal covering: each step, the candidate that newly covers the most demand."""

from __future__ import annotations

import numpy as np

from hydgap.optimize.base import SiteChoice, SitingProblem, SitingResult


class GreedySiter:
    def solve(self, p: SitingProblem) -> SitingResult:
        covered = p.covered0.copy()
        chosen = np.zeros(p.n, dtype=bool)
        result = SitingResult(
            baseline_covered=float(p.demand[covered].sum()),
            total_demand=float(p.demand.sum()),
        )
        spent = 0.0
        cumulative = 0.0
        is_candidate = np.zeros(p.n, dtype=bool)
        is_candidate[p.candidates] = True
        while True:
            uncovered_demand = p.demand * (~covered)
            gains = np.asarray(p.neighbors @ uncovered_demand).ravel()
            mask = is_candidate & ~chosen & (p.costs <= p.budget - spent + 1e-12)
            if not mask.any():
                break
            gains = np.where(mask, gains, -np.inf)
            best = int(np.argmax(gains))
            if gains[best] <= 0:
                break
            newly = p.neighbors[best].indices
            covered[newly] = True
            chosen[best] = True
            spent += float(p.costs[best])
            cumulative += float(gains[best])
            result.sites.append(
                SiteChoice(
                    order=len(result.sites) + 1,
                    cell_id=str(p.cell_ids[best]),
                    marginal_gain=float(gains[best]),
                    cumulative_gain=cumulative,
                    cost=float(p.costs[best]),
                    spent=spent,
                )
            )
        result.total_gain = cumulative
        result.spent = spent
        return result
