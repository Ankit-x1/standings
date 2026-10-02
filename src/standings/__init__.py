"""Independent Poisson models for Premier League results and standings."""

from .data import DataValidationError, load_matches, rebuild_standings
from .models import fit_m0, fit_m1
from .probability import outcome_probabilities, skellam_probabilities

__version__ = "0.1.0"

__all__ = [
    "DataValidationError",
    "load_matches",
    "rebuild_standings",
    "fit_m0",
    "fit_m1",
    "outcome_probabilities",
    "skellam_probabilities",
]
