"""Exact maximal covering as an integer programme: the swap-in for GreedySiter.

Formulation (PuLP / CBC), same SitingProblem in, same SitingResult out:

    x_j in {0,1}   place a station at candidate cell j
    y_i in {0,1}   cell i is covered
    maximise  sum_i demand_i * y_i
    s.t.      y_i <= covered0_i + sum_{j in N(i)} x_j     for every cell i
              sum_j cost_j * x_j <= budget

N(i) is row i of the neighbours matrix. Marginal gains for the curve come
from re-solving at budgets 1..B or from ordering the chosen sites greedily
after the fact. Not implemented in v1; `uv add pulp` and fill in `solve`.
"""

from __future__ import annotations

from hydgap.optimize.base import SitingProblem, SitingResult


class ILPSiter:
    def solve(self, problem: SitingProblem) -> SitingResult:
        raise NotImplementedError("ILPSiter is a documented extension point; see the module docstring")
