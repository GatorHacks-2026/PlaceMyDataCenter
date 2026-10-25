"""Project identity must not collapse distinct sites owned by one company."""

from scripts.ecocompute_research.identity import IdentificationStatus, identify_project
from scripts.ecocompute_research.location import parse_location


def test_cnbc_style_pine_island_seed_selects_exact_facility():
    text = (
        "Google says its planned 780-megawatt data center in Pine Island, "
        "Minnesota, could offer a model for powering the AI boom. "
        "Other data centers are changing America's grid."
    )
    result = identify_project(text, parse_location("Pine Island, MN"))
    assert result.status == IdentificationStatus.SELECTED
    assert result.selected.developer == "Google"
    assert result.selected.location.city == "Pine Island"
    assert result.selected.location.state == "MN"
    assert result.selected.location.latitude is None


def test_city_in_project_sentence_and_state_elsewhere_selects_project():
    text = (
        "Pine Island, Minnesota, is a small town. "
        "Google hopes its new 780-megawatt data center plan will help the Pine Island community. "
        "Data centers elsewhere face grid constraints."
    )
    result = identify_project(text, parse_location("Pine Island, MN"))
    assert result.status == IdentificationStatus.SELECTED
    assert result.selected.developer == "Google"
    assert result.selected.name_is_reported is False


def test_city_only_without_state_stays_unresolved():
    result = identify_project(
        "Google hopes its data center plan will help the Pine Island community.",
        parse_location("Pine Island, MN"),
    )
    assert result.status == IdentificationStatus.NOT_FOUND


def test_same_company_different_city_is_not_merged():
    text = (
        "Google announced a data center in Pine Island, MN. "
        "Google also proposed a data center in Hermantown, MN."
    )
    focused = identify_project(text, parse_location("Pine Island, MN"))
    assert focused.status == IdentificationStatus.SELECTED
    assert focused.selected.location.city == "Pine Island"
    assert {item.project.location.city for item in focused.candidates} == {
        "Pine Island", "Hermantown",
    }
    assert all(item.project.developer == "Google" for item in focused.candidates)

    statewide = identify_project(text, parse_location("Minnesota"))
    assert statewide.status == IdentificationStatus.AMBIGUOUS
    assert statewide.selected is None
    assert len(statewide.candidates) == 2


def test_same_city_two_companies_stays_ambiguous():
    text = (
        "Google proposed a data center in Pine Island, MN. "
        "Amazon proposed a data center in Pine Island, MN."
    )
    result = identify_project(text, parse_location("Pine Island, MN"))
    assert result.status == IdentificationStatus.AMBIGUOUS
    assert result.selected is None
    assert {item.project.developer for item in result.candidates} == {"Google", "Amazon"}


def test_location_mismatch_and_generic_grid_article_do_not_invent_project():
    mismatch = identify_project(
        "Google announced a data center in Hermantown, MN.",
        parse_location("Pine Island, MN"),
    )
    assert mismatch.status == IdentificationStatus.NOT_FOUND
    assert mismatch.selected is None
    assert len(mismatch.candidates) == 1

    generic = identify_project(
        "Data centers across Minnesota are putting pressure on the grid.",
        parse_location("Minnesota"),
    )
    assert generic.status == IdentificationStatus.NOT_FOUND
    assert generic.candidates == []


def test_location_only_requires_discovery():
    result = identify_project(None, parse_location("Texas"))
    assert result.status == IdentificationStatus.NOT_FOUND
    assert "discovery" in result.explanation


def test_project_alias_and_explicit_announcement_date():
    result = identify_project(
        "Google announced on February 24, 2026 that Project Skyway is a planned "
        "data center in Pine Island, MN.",
        parse_location("Pine Island, MN"),
    )
    assert result.status == IdentificationStatus.SELECTED
    assert result.selected.name == "Project Skyway"
    assert result.selected.name_is_reported is True
    assert result.selected.announced_on.isoformat() == "2026-02-24"


def test_explicit_operator_and_alias_are_kept_separate_from_developer():
    result = identify_project(
        "Project Skyway, also known as Pine Island Campus, is a data center "
        "developed by Tract and operated by Google in Pine Island, MN.",
        parse_location("Pine Island, MN"),
    )
    assert result.status == IdentificationStatus.SELECTED
    assert result.selected.developer == "Tract"
    assert result.selected.operator == "Google"
    assert result.selected.aliases == ["Pine Island Campus"]
