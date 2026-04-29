"""Yamada-style transition matrix and fundamental matrix utilities."""

from __future__ import annotations

import numpy as np


# Latest MATLAB logic uses a lookup-table classification for chemistry-specific
# lifetime behavior, cascade split, and loop multiplier. These values are ported
# directly from the newest MATLAB source.
BATTERY_PROPERTIES = {
    # High cascade / open-loop group
    "LFP": {
        "w_mean": 3.48,
        "w_std": 0.20,
        "casc_min": 0.70,
        "casc_max": 0.90,
        "loop_rate": 0.10,
    },
    "LMO": {
        "w_mean": 2.50,
        "w_std": 0.30,
        "casc_min": 0.50,
        "casc_max": 0.80,
        "loop_rate": 0.10,
    },
    # Balanced value group
    "NMC111": {
        "w_mean": 3.30,
        "w_std": 0.20,
        "casc_min": 0.40,
        "casc_max": 0.60,
        "loop_rate": 1.0,
    },
    "NMC523": {
        "w_mean": 3.30,
        "w_std": 0.20,
        "casc_min": 0.30,
        "casc_max": 0.50,
        "loop_rate": 1.0,
    },
    "NMC622": {
        "w_mean": 3.30,
        "w_std": 0.20,
        "casc_min": 0.20,
        "casc_max": 0.40,
        "loop_rate": 1.0,
    },
    # High-Ni / high-value group
    "NMC811": {
        "w_mean": 3.00,
        "w_std": 0.25,
        "casc_min": 0.05,
        "casc_max": 0.15,
        "loop_rate": 1.0,
    },
    "NCA": {
        "w_mean": 3.00,
        "w_std": 0.25,
        "casc_min": 0.05,
        "casc_max": 0.15,
        "loop_rate": 1.0,
    },
}

# Compatibility aliases for user-facing chemistry names.
BATTERY_ALIASES = {
    "NMC532": "NMC523",
}


def _clean_battery_type(battery_type: str) -> str:
    """Normalize chemistry labels such as 'NMC(811)' into lookup keys like 'NMC811'."""
    return "".join(ch for ch in str(battery_type) if ch.isalnum()).upper()


def _get_battery_properties(battery_type: str):
    """
    Fetch chemistry-specific parameters from the latest MATLAB lookup table.

    Unknown chemistry falls back to the latest MATLAB default NMC-like values.
    """
    clean_type = _clean_battery_type(battery_type)
    clean_type = BATTERY_ALIASES.get(clean_type, clean_type)

    if clean_type in BATTERY_PROPERTIES:
        return BATTERY_PROPERTIES[clean_type]

    print(
        f"Warning: Unknown battery type {battery_type}, using default balanced NMC parameters."
    )
    return {
        "w_mean": 3.30,
        "w_std": 0.20,
        "casc_min": 0.30,
        "casc_max": 0.50,
        "loop_rate": 1.0,
    }


def Construct_Yamada_Matrix(
    subsidy: float,
    battery_type: str,
    base_r_input: float,
    subsidy_alpha: float = 0.5,
):
    """
    Build the 6x6 Yamada-style transition matrix for the current scenario.

    The latest MATLAB source uses a chemistry lookup table instead of only
    two hard-coded battery branches. The effective recovery rate still follows
    the EverBatt base recovery value, with a small stochastic perturbation and
    an optional loop multiplier depending on chemistry class.
    """
    base_r = base_r_input

    props = _get_battery_properties(battery_type)
    weibull_alpha = np.random.normal(props["w_mean"], props["w_std"])
    cascade_cap = np.random.uniform(props["casc_min"], props["casc_max"])
    loop_multiplier = props["loop_rate"]

    early_fail_factor = 3.5 / weibull_alpha
    prob_early_recycle = 0.02 * early_fail_factor
    prob_early_landfill = 0.01 * early_fail_factor
    prob_aging = max(0.0, 1.0 - prob_early_recycle - prob_early_landfill)

    base_ev_collection = 0.25
    max_policy_ceiling = 0.90
    collection_rate_cascade = 0.98
    subsidy_k = (max_policy_ceiling / base_ev_collection) - 1.0

    collection_rate_ev = base_ev_collection * (1.0 + subsidy_k * (subsidy**subsidy_alpha))
    collection_rate_ev = min(collection_rate_ev, max_policy_ceiling)

    prob_to_cascade = cascade_cap

    # Keep the small stochastic perturbation used by the latest MATLAB version.
    r_gain = np.random.normal(0.0, 0.005)
    r_effective = min(max(base_r + r_gain, 0.0), 0.98) * loop_multiplier

    A = np.zeros((6, 6), dtype=float)
    A[0, 1] = 1.0
    A[1, 2] = prob_aging
    A[1, 4] = prob_early_recycle
    A[1, 5] = prob_early_landfill
    A[2, 3] = prob_to_cascade

    rest_from_ev = 1.0 - prob_to_cascade
    A[2, 4] = rest_from_ev * collection_rate_ev
    A[2, 5] = rest_from_ev * (1.0 - collection_rate_ev)

    A[3, 4] = collection_rate_cascade
    A[3, 5] = 1.0 - collection_rate_cascade
    A[4, 0] = r_effective
    A[4, 5] = 1.0 - r_effective
    A[5, 5] = 1.0

    return A, r_effective


def Calculate_Yamada_N_Matrix(A: np.ndarray):
    """Compute the fundamental matrix N = (I - Q)^(-1) and the Yamada N value."""
    Q = A[:5, :5]
    I = np.eye(5)
    try:
        N_mat = np.linalg.inv(I - Q)
    except np.linalg.LinAlgError:
        N_mat = np.zeros((5, 5), dtype=float)
    N_value = N_mat[0, 1]
    return N_value, N_mat
