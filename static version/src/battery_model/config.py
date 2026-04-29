"""Shared data containers and lightweight configuration objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContextParams:
    Country: str
    Feedstock_tonnes: float
    Throughput_GWh: float


@dataclass
class GHGVectors:
    E_mfg: float = 0.0
    E_trans: float = 0.0
    E_loop: float = 0.0


@dataclass
class CostVectors:
    C_mfg: float = 0.0
    C_trans: float = 0.0
    C_loop: float = 0.0
    C_casc_net: float = 0.0


@dataclass
class TechConfig:
    process: str
    regen: str


@dataclass
class Scenario:
    subsidy: float
    subsidy_alpha: float = 0.5
