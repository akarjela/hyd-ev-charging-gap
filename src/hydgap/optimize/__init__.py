from hydgap.optimize.base import Siter, SitingProblem, SitingResult, UniformCost, build_problem
from hydgap.optimize.greedy import GreedySiter

SOLVERS: dict[str, type] = {"greedy": GreedySiter}

__all__ = ["SOLVERS", "GreedySiter", "Siter", "SitingProblem", "SitingResult", "UniformCost", "build_problem"]
