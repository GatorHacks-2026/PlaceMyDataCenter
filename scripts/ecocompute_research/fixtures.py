"""Small offline contract fixture. This does not perform or replace research."""

from datetime import date

from .models import (
    CapacityKind,
    Claim,
    ClaimSubject,
    EvidenceRef,
    EvidenceStatus,
    Location,
    LocationPrecision,
    MissingField,
    ProjectIdentity,
    ProjectPhase,
    ResearchResult,
    ResearchStatus,
    SourceRecord,
    SourceType,
)


def pine_island_contract_fixture() -> ResearchResult:
    """The four distinct MW subjects used to validate the research contract.

    Source snippets are short excerpts from the accessible secondary report
    and Google's announcement. The supplied CNBC article was not fetched for
    this offline fixture, and no regulatory filings are included.
    """
    return ResearchResult(
        status=ResearchStatus.PARTIAL,
        project=ProjectIdentity(
            name="Google Pine Island data center",
            developer="Google",
            location=Location(
                city="Pine Island",
                state="MN",
                precision=LocationPrecision.CITY,
            ),
            phase=ProjectPhase.PROPOSED,
        ),
        sources=[
            SourceRecord(
                id="blandin_2026_10_19",
                title="Google hopes that its new data center plan will build goodwill",
                source_type=SourceType.NEWS,
                independent_origin="cnbc_2026_10_19_reporting",
                url="https://blandinonbroadband.org/2026/10/19/google-hopes-that-its-new-data-center-plan-will-build-goodwill-with-the-pine-island-goodhue-county/",
                published_on=date(2026, 10, 19),
            ),
            SourceRecord(
                id="google_2026_02_24",
                title="Google is coming to Minnesota and advancing clean energy goals",
                source_type=SourceType.COMPANY,
                independent_origin="google_2026_02_24_announcement",
                url="https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/data-center-pine-island/",
                published_on=date(2026, 2, 24),
            ),
        ],
        claims=[
            Claim(
                id="facility_780_mw",
                field="electricity.capacity_mw",
                subject=ClaimSubject.DATA_CENTER,
                measure="power_capacity",
                value=780,
                unit="MW",
                capacity_kind=CapacityKind.UNKNOWN,
                phase=ProjectPhase.PROPOSED,
                status=EvidenceStatus.REPORTED,
                evidence=[EvidenceRef(
                    source_id="blandin_2026_10_19",
                    excerpt="new 780-megawatt data center plan",
                )],
            ),
            Claim(
                id="wind_1400_mw",
                field="energy_plan.wind_capacity_mw",
                subject=ClaimSubject.WIND_GENERATION,
                measure="power_capacity",
                value=1400,
                unit="MW",
                phase=ProjectPhase.PROPOSED,
                status=EvidenceStatus.REPORTED,
                evidence=[EvidenceRef(
                    source_id="google_2026_02_24",
                    excerpt="1,400 megawatts (MW) of wind",
                )],
            ),
            Claim(
                id="solar_200_mw",
                field="energy_plan.solar_capacity_mw",
                subject=ClaimSubject.SOLAR_GENERATION,
                measure="power_capacity",
                value=200,
                unit="MW",
                phase=ProjectPhase.PROPOSED,
                status=EvidenceStatus.REPORTED,
                evidence=[EvidenceRef(
                    source_id="google_2026_02_24",
                    excerpt="200 MW of solar",
                )],
            ),
            Claim(
                id="battery_300_mw",
                field="energy_plan.battery_power_mw",
                subject=ClaimSubject.BATTERY_STORAGE,
                measure="power_capacity",
                value=300,
                unit="MW",
                phase=ProjectPhase.PROPOSED,
                status=EvidenceStatus.REPORTED,
                evidence=[EvidenceRef(
                    source_id="google_2026_02_24",
                    excerpt="300 MW of iron-air battery storage",
                )],
            ),
        ],
        missing_fields=[
            MissingField(
                field="water.peak_daily_gallons",
                severity="critical",
                why_it_matters="Peak demand determines stress on a local water system.",
                checked_source_ids=["blandin_2026_10_19", "google_2026_02_24"],
                town_hall_question="What is the project's expected peak daily water demand?",
            ),
            MissingField(
                field="cooling.type",
                severity="warning",
                why_it_matters="Cooling design affects direct water and electricity use.",
                checked_source_ids=["blandin_2026_10_19", "google_2026_02_24"],
                town_hall_question="What cooling design is proposed for this facility?",
            ),
        ],
        limitations=[
            "Offline schema fixture only; source access and comprehensive discovery have not run.",
            "The supplied CNBC article was not fetched; the 780 MW excerpt comes from a secondary report quoting CNBC.",
            "The 780 MW report does not identify IT versus facility versus grid connection capacity.",
        ],
    )
