"""Tests for custom_components.hass_ledvance.schema_parser."""
from __future__ import annotations

import pytest

from custom_components.hass_ledvance.schema_parser import (
    detect_device_type,
    get_dps_map,
    get_enum_range,
    get_integer_range,
    get_numeric_scale,
    get_socket_outlet_dps,
    has_hardware_master,
)


# ---------------------------------------------------------------------------
# detect_device_type
# ---------------------------------------------------------------------------

class TestDetectDeviceType:
    def test_thermostat_gen1(self, thermostat_gen1_schema):
        assert detect_device_type(thermostat_gen1_schema, "any_product") == "thermostat"

    def test_thermostat_gen2(self, thermostat_gen2_schema):
        assert detect_device_type(thermostat_gen2_schema, "any_product") == "thermostat"

    def test_thermostat_takes_precedence_over_switch(self):
        schema = [
            {"id": 1, "code": "switch",   "type": "Boolean", "mode": "rw"},
            {"id": 2, "code": "temp_set", "type": "Integer", "mode": "rw"},
        ]
        assert detect_device_type(schema, "any") == "thermostat"

    def test_lightstrip_detected_as_light(self, lightstrip_schema):
        assert detect_device_type(lightstrip_schema, "any_product") == "light"

    def test_light_via_switch_led(self):
        schema = [{"id": 20, "code": "switch_led", "type": "Boolean", "mode": "rw"}]
        assert detect_device_type(schema, "any") == "light"

    def test_light_via_bright_value(self, light_schema):
        assert detect_device_type(light_schema, "any_product") == "light"

    def test_light_via_colour_data(self, rgb_light_schema):
        assert detect_device_type(rgb_light_schema, "any_product") == "light"

    def test_light_via_temp_value_only(self):
        schema = [{"id": 1, "code": "temp_value", "type": "Integer", "mode": "rw"}]
        assert detect_device_type(schema, "any") == "light"

    def test_socket_strip_multiple_numbered_switches(self, socket_strip_schema):
        assert detect_device_type(socket_strip_schema, "any") == "socket_strip"

    def test_socket_strip_requires_two_or_more_numbered(self):
        """A single switch_1 is still just a switch, not a strip."""
        schema = [{"id": 1, "code": "switch_1", "type": "Boolean", "mode": "rw"}]
        assert detect_device_type(schema, "any") == "switch"

    def test_single_switch(self, single_switch_schema):
        assert detect_device_type(single_switch_schema, "any") == "switch"

    def test_switch_keyword(self):
        schema = [{"id": 1, "code": "switch_led_off", "type": "Boolean", "mode": "rw"}]
        # "switch_led_off" starts with "switch" but is not a light code → switch
        assert detect_device_type(schema, "any") == "switch"

    def test_unknown_falls_back_to_product_id(self):
        schema = [{"id": 1, "code": "some_unknown_code", "type": "Raw", "mode": "rw"}]
        assert detect_device_type(schema, "pq860vo9ib50jhud") == "switch"

    def test_unknown_product_id_returns_unknown(self):
        schema = [{"id": 1, "code": "some_unknown_code", "type": "Raw", "mode": "rw"}]
        assert detect_device_type(schema, "not_in_table") == "unknown"

    def test_empty_schema_with_unknown_product(self):
        assert detect_device_type([], "not_in_table") == "unknown"

    def test_light_takes_precedence_over_numbered_switches(self):
        """If a device has both light DPS and numbered switch DPS, it's a light."""
        schema = [
            {"id": 1, "code": "switch_1",     "type": "Boolean", "mode": "rw"},
            {"id": 2, "code": "switch_2",     "type": "Boolean", "mode": "rw"},
            {"id": 3, "code": "bright_value", "type": "Integer", "mode": "rw"},
        ]
        assert detect_device_type(schema, "any") == "light"


# ---------------------------------------------------------------------------
# get_dps_map
# ---------------------------------------------------------------------------

class TestGetDpsMap:
    def test_basic_mapping(self, light_schema):
        result = get_dps_map(light_schema)
        assert result == {
            "switch_led":   "1",
            "work_mode":    "2",
            "bright_value": "3",
            "temp_value":   "4",
        }

    def test_returns_string_ids(self, socket_strip_schema):
        result = get_dps_map(socket_strip_schema)
        for v in result.values():
            assert isinstance(v, str)

    def test_skips_items_missing_code_or_id(self):
        schema = [
            {"id": 1, "code": "switch"},
            {"code": "no_id"},           # missing id → skipped
            {"id": 3},                   # missing code → skipped
        ]
        result = get_dps_map(schema)
        assert result == {"switch": "1"}

    def test_empty_schema(self):
        assert get_dps_map([]) == {}


# ---------------------------------------------------------------------------
# get_integer_range
# ---------------------------------------------------------------------------

class TestGetIntegerRange:
    def test_reads_min_max(self, light_schema):
        assert get_integer_range(light_schema, "bright_value") == (10, 1000)

    def test_default_when_code_not_found(self, light_schema):
        assert get_integer_range(light_schema, "nonexistent") == (0, 1000)

    def test_parses_json_string_property(self):
        import json
        schema = [
            {"id": 1, "code": "temp",
             "property": json.dumps({"min": 5, "max": 500, "scale": 0})}
        ]
        assert get_integer_range(schema, "temp") == (5, 500)

    def test_missing_property_uses_defaults(self):
        schema = [{"id": 1, "code": "val"}]
        assert get_integer_range(schema, "val") == (0, 1000)


# ---------------------------------------------------------------------------
# get_numeric_scale
# ---------------------------------------------------------------------------

class TestGetNumericScale:
    def test_scale_3_gives_divisor_1000(self, socket_strip_schema):
        assert get_numeric_scale(socket_strip_schema, "cur_current") == 1000.0

    def test_scale_1_gives_divisor_10(self, socket_strip_schema):
        assert get_numeric_scale(socket_strip_schema, "cur_voltage") == 10.0

    def test_scale_0_gives_divisor_1(self, light_schema):
        # bright_value has scale 0
        assert get_numeric_scale(light_schema, "bright_value") == 1.0

    def test_missing_code_returns_1(self, light_schema):
        assert get_numeric_scale(light_schema, "nonexistent") == 1.0

    def test_missing_scale_key_defaults_to_0(self):
        schema = [{"id": 1, "code": "val", "property": {"min": 0, "max": 100}}]
        assert get_numeric_scale(schema, "val") == 1.0


# ---------------------------------------------------------------------------
# get_enum_range
# ---------------------------------------------------------------------------

class TestGetEnumRange:
    def test_reads_range(self, light_schema):
        result = get_enum_range(light_schema, "work_mode")
        assert result == ["white", "colour", "scene"]

    def test_missing_code_returns_empty(self, light_schema):
        assert get_enum_range(light_schema, "nonexistent") == []

    def test_empty_range(self):
        schema = [{"id": 1, "code": "mode", "property": {"range": []}}]
        assert get_enum_range(schema, "mode") == []


# ---------------------------------------------------------------------------
# get_socket_outlet_dps
# ---------------------------------------------------------------------------

class TestGetSocketOutletDps:
    def test_numbered_outlets_sorted(self, socket_strip_schema):
        result = get_socket_outlet_dps(socket_strip_schema)
        codes = [code for code, _ in result]
        assert codes[:3] == ["switch_1", "switch_2", "switch_3"]

    def test_labels_use_outlet_number(self, socket_strip_schema):
        result = get_socket_outlet_dps(socket_strip_schema)
        labels = [label for _, label in result]
        assert labels[:3] == ["Outlet 1", "Outlet 2", "Outlet 3"]

    def test_hardware_master_appended_last(self, socket_strip_with_master_schema):
        result = get_socket_outlet_dps(socket_strip_with_master_schema)
        assert result[-1] == ("master_switch", "All Outlets")

    def test_no_master_in_result_when_absent(self, socket_strip_schema):
        result = get_socket_outlet_dps(socket_strip_schema)
        codes = [code for code, _ in result]
        assert "master_switch" not in codes
        assert "switch_all" not in codes

    def test_usb_switch_included(self):
        schema = [
            {"id": 1, "code": "switch_1",   "type": "Boolean", "mode": "rw"},
            {"id": 2, "code": "switch_2",   "type": "Boolean", "mode": "rw"},
            {"id": 3, "code": "usb_switch", "type": "Boolean", "mode": "rw"},
        ]
        result = get_socket_outlet_dps(schema)
        codes = [code for code, _ in result]
        assert "usb_switch" in codes
        assert result[[c for c, _ in result].index("usb_switch")][1] == "USB"

    def test_numbered_usb_ports_included(self):
        schema = [
            {"id": 1, "code": "switch_1",    "type": "Boolean", "mode": "rw"},
            {"id": 2, "code": "switch_2",    "type": "Boolean", "mode": "rw"},
            {"id": 3, "code": "switch_usb1", "type": "Boolean", "mode": "rw"},
            {"id": 4, "code": "switch_usb2", "type": "Boolean", "mode": "rw"},
        ]
        result = get_socket_outlet_dps(schema)
        codes = [code for code, _ in result]
        assert "switch_usb1" in codes
        assert "switch_usb2" in codes

    def test_switch_all_used_when_no_master_switch(self):
        schema = [
            {"id": 1, "code": "switch_1",  "type": "Boolean", "mode": "rw"},
            {"id": 2, "code": "switch_2",  "type": "Boolean", "mode": "rw"},
            {"id": 3, "code": "switch_all", "type": "Boolean", "mode": "rw"},
        ]
        result = get_socket_outlet_dps(schema)
        assert result[-1] == ("switch_all", "All Outlets")

    def test_master_switch_preferred_over_switch_all(self):
        schema = [
            {"id": 1, "code": "switch_1",     "type": "Boolean", "mode": "rw"},
            {"id": 2, "code": "switch_2",     "type": "Boolean", "mode": "rw"},
            {"id": 3, "code": "master_switch", "type": "Boolean", "mode": "rw"},
            {"id": 4, "code": "switch_all",    "type": "Boolean", "mode": "rw"},
        ]
        result = get_socket_outlet_dps(schema)
        # master_switch wins; switch_all should not appear
        master_entries = [(c, l) for c, l in result if c in ("master_switch", "switch_all")]
        assert len(master_entries) == 1
        assert master_entries[0][0] == "master_switch"

    def test_empty_schema(self):
        assert get_socket_outlet_dps([]) == []


# ---------------------------------------------------------------------------
# has_hardware_master
# ---------------------------------------------------------------------------

class TestHasHardwareMaster:
    def test_true_for_master_switch(self, socket_strip_with_master_schema):
        assert has_hardware_master(socket_strip_with_master_schema) is True

    def test_true_for_switch_all(self):
        schema = [{"id": 1, "code": "switch_all", "type": "Boolean", "mode": "rw"}]
        assert has_hardware_master(schema) is True

    def test_false_when_no_master(self, socket_strip_schema):
        assert has_hardware_master(socket_strip_schema) is False

    def test_false_for_empty_schema(self):
        assert has_hardware_master([]) is False
