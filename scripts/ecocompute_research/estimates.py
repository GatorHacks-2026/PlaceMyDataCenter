"""Configurable provisional MW proxies, separate from reported project facts."""

from __future__ import annotations

from pydantic import Field

from .models import (
    CapacityKind, Claim, ClaimSubject, EvidenceStatus, StrictModel,
)


class ProxyConfig(StrictModel):
    ai_mw_per_10k_sqft: float = Field(default=3.5, gt=0)
    cloud_mw_per_10k_sqft: float = Field(default=2.5, gt=0)
    investment_million_usd_per_mw: float = Field(default=10.0, gt=0)
    mw_per_acre: float = Field(default=0.8, gt=0)
    scenario_baseline_mw: float = Field(default=100.0, gt=0)


class ScaleAssessment(StrictModel):
    reported_capacity_mw: float | None = None
    reported_capacity_kind: CapacityKind | None = None
    proxy_claim: Claim | None = None
    scenario_baseline_mw: float
    limitations: list[str] = Field(default_factory=list)


def _single_numeric(claims: list[Claim], field: str) -> float | None:
    values = {float(claim.value) for claim in claims
              if claim.field == field and isinstance(claim.value, (int, float))
              and claim.status not in {EvidenceStatus.CONFLICTING, EvidenceStatus.NOT_FOUND}}
    return next(iter(values)) if len(values) == 1 else None


def assess_scale(
    claims: list[Claim], *, workload_type: str = "unspecified",
    config: ProxyConfig | None = None,
) -> ScaleAssessment:
    config = config or ProxyConfig()
    reported = [claim for claim in claims
                if claim.field == "electricity.capacity_mw"
                and claim.subject == ClaimSubject.DATA_CENTER
                and claim.status in {EvidenceStatus.REPORTED, EvidenceStatus.VERIFIED}]
    if len(reported) == 1:
        return ScaleAssessment(
            reported_capacity_mw=float(reported[0].value),
            reported_capacity_kind=reported[0].capacity_kind,
            scenario_baseline_mw=config.scenario_baseline_mw,
            limitations=["Reported capacity is not automatically IT capacity."],
        )

    sqft = _single_numeric(claims, "project.building_sqft")
    investment = _single_numeric(claims, "financial.investment_usd")
    acreage = _single_numeric(claims, "project.land_acres")
    if sqft and sqft > 0:
        density = config.ai_mw_per_10k_sqft if workload_type == "ai_training" else config.cloud_mw_per_10k_sqft
        value = sqft / 10_000 * density
        assumption = f"Preliminary proxy: {density} MW per 10,000 building square feet."
    elif investment and investment > 0:
        value = investment / 1_000_000 / config.investment_million_usd_per_mw
        assumption = f"Preliminary proxy: ${config.investment_million_usd_per_mw:g} million per MW of capital investment."
    elif acreage and acreage > 0:
        value = acreage * config.mw_per_acre
        assumption = f"Preliminary proxy: {config.mw_per_acre:g} MW per acre."
    else:
        return ScaleAssessment(
            scenario_baseline_mw=config.scenario_baseline_mw,
            limitations=["Project capacity was not found; the baseline is only a user scenario."],
        )
    proxy = Claim(
        id="estimated_proxy_capacity", field="electricity.proxy_capacity_mw",
        subject=ClaimSubject.DATA_CENTER, measure="power_capacity",
        value=round(value, 1), unit="MW", capacity_kind=CapacityKind.UNKNOWN,
        status=EvidenceStatus.ESTIMATED,
        assumptions=[assumption, "This proxy is not a verified engineering capacity."],
    )
    return ScaleAssessment(
        proxy_claim=proxy,
        scenario_baseline_mw=config.scenario_baseline_mw,
        limitations=["The directly disclosed capacity remains missing; the proxy is not site evidence."],
    )
