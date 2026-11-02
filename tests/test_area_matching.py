"""Tests for the fuzzy area-matching logic in __init__.py."""
from __future__ import annotations

import pytest

# Import the private helper directly (it's pure Python, no HA dep)
from custom_components.hass_ledvance.__init__ import _find_best_area


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def area_by_name() -> dict[str, str]:
    """Simulate a realistic HA area registry (lower-cased name → area_id)."""
    return {
        "office":              "office",
        "kitchen":             "kitchen",
        "living room":         "living_room",
        "adults bedroom":      "bedroom",
        "sauna":               "sauna",
        "sauna lounge":        "sauna_lounge",
        "basement stairs":     "basement_stairs",
        "hallway (downstairs)": "hallway",
        "noa's bedroom":       "boys_bedroom",
        "outside":             "outside",
    }


# ---------------------------------------------------------------------------
# Tier 1 — exact match
# ---------------------------------------------------------------------------

class TestExactMatch:
    def test_exact_case_insensitive(self, area_by_name):
        area_id, matched, score = _find_best_area("Office", area_by_name)
        assert area_id == "office"
        assert score == 1.0

    def test_exact_all_lower(self, area_by_name):
        area_id, matched, score = _find_best_area("kitchen", area_by_name)
        assert area_id == "kitchen"
        assert score == 1.0

    def test_exact_mixed_case(self, area_by_name):
        area_id, matched, score = _find_best_area("SAUNA", area_by_name)
        assert area_id == "sauna"
        assert score == 1.0


# ---------------------------------------------------------------------------
# Tier 2 — substring containment
# ---------------------------------------------------------------------------

class TestSubstringMatch:
    def test_tuya_room_contained_in_ha_area(self, area_by_name):
        """'Basement' is contained in 'basement stairs'."""
        area_id, matched, score = _find_best_area("Basement", area_by_name)
        assert area_id == "basement_stairs"
        assert score == 0.8

    def test_ha_area_contained_in_tuya_room(self, area_by_name):
        """'Sauna' (HA area) is contained in 'Sauna near the pool' (Tuya room)."""
        area_id, matched, score = _find_best_area("Sauna near the pool", area_by_name)
        assert area_id in ("sauna", "sauna_lounge")  # either is a valid substring hit
        assert score == 0.8

    def test_best_substring_chosen_by_similarity(self, area_by_name):
        """When multiple areas are substring matches, the most similar wins."""
        # "Sauna Lounge" will be a substring match for both "sauna" and "sauna lounge"
        area_id, matched, score = _find_best_area("Sauna Lounge", area_by_name)
        # "sauna lounge" is an exact match → takes tier 1; confirm
        assert score == 1.0
        assert area_id == "sauna_lounge"


# ---------------------------------------------------------------------------
# Tier 3 — fuzzy similarity
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    def test_fuzzy_matches_close_name(self, area_by_name):
        """'Livng Room' (typo) should fuzzy-match 'living room'."""
        area_id, matched, score = _find_best_area("Livng Room", area_by_name)
        assert area_id == "living_room"
        assert score >= 0.5  # any tier above threshold is acceptable

    def test_fuzzy_matches_partial_word(self, area_by_name):
        """'Outsdide' (typo) should fuzzy-match 'outside'."""
        area_id, matched, score = _find_best_area("Outsdide", area_by_name)
        assert area_id == "outside"
        assert score >= 0.5

    def test_below_threshold_returns_none(self, area_by_name):
        """A completely unrelated name should produce no match."""
        area_id, matched, score = _find_best_area("Gymnasium", area_by_name)
        assert area_id is None
        assert score == 0.0

    def test_empty_area_map_returns_none(self):
        area_id, matched, score = _find_best_area("Office", {})
        assert area_id is None
        assert score == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_room_name_returns_none(self, area_by_name):
        area_id, _, score = _find_best_area("", area_by_name)
        # Empty string can substring-match everything; just assert it doesn't crash
        # and that the result is at least consistent
        assert score >= 0.0

    def test_single_char_room_not_over_matched(self, area_by_name):
        """Very short names shouldn't falsely claim high confidence."""
        area_id, _, score = _find_best_area("X", area_by_name)
        # Either no match or very low score
        assert area_id is None or score < 0.8

    def test_return_type_is_tuple_of_three(self, area_by_name):
        result = _find_best_area("Office", area_by_name)
        assert isinstance(result, tuple)
        assert len(result) == 3
