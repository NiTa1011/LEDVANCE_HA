"""Constants for the Ledvance/Tuya integration."""

DOMAIN = "hass_ledvance"
PLATFORMS = ["binary_sensor", "climate", "light", "number", "sensor", "switch"]

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_REGION = "region"

# Coordinator / polling
DEFAULT_SCAN_INTERVAL = 30  # seconds
LAN_SCAN_INTERVAL = 300     # rescan LAN every 5 minutes

# Ledvance app credentials (reverse-engineered from mobile app)
TUYA_CLIENT_ID = "fx3fvkvusmw45d7jn8xh"
TUYA_SECRET_KEY = "A_armptsqyfpxa4ftvtc739ardncett3uy_cgqx3ku34mh5qdesd7fcaru3gx7tyurr"
TUYA_USER_AGENT = "TY-UA=APP/Android/1.1.6/SDK/null"
TUYA_DEVICE_ID = "5fe5abb36728cce7b9cd2185625edccbd6d9bd787e40"

# Sylvania variant (uncomment and replace above if using Sylvania)
# TUYA_CLIENT_ID = "creq75hn4vdg5qvrgryp"
# TUYA_SECRET_KEY = "A_ag4xcmp9rjttkj9yf9e8c3wfxry7yr44_wparh3scdv8dc7rrnuegaf9mqmn4snpk"

# Region definitions: endpoint URL + default country code
REGIONS: dict[str, dict] = {
    "EU":    {"endpoint": "https://a1.tuyaeu.com/api.json", "country_code": 49},
    "US":    {"endpoint": "https://a1.tuyaus.com/api.json", "country_code": 1},
    "China": {"endpoint": "https://a1.tuyacn.com/api.json", "country_code": 86},
    "India": {"endpoint": "https://a1.tuyain.com/api.json", "country_code": 91},
}
DEFAULT_REGION = "EU"

# DPS code names (standard Tuya naming)
DPS_SWITCH_LED = "switch_led"
DPS_WORK_MODE = "work_mode"
DPS_BRIGHT_VALUE = "bright_value"
DPS_BRIGHT_VALUE_V2 = "bright_value_v2"
DPS_TEMP_VALUE = "temp_value"
DPS_TEMP_VALUE_V2 = "temp_value_v2"
DPS_COLOUR_DATA = "colour_data"
DPS_COLOUR_DATA_V2 = "colour_data_v2"
DPS_COLOUR_DATA_HSV = "colour_data_hsv"
DPS_SCENE_DATA = "scene_data"
DPS_SCENE_DATA_V2 = "scene_data_v2"

# Thermostat (Gen 1 & Gen 2) DPS codes
DPS_TEMP_SET = "temp_set"
DPS_TEMP_CURRENT = "temp_current"
DPS_VALVE_STATE = "valve_state"
DPS_WINDOW_STATE = "window_state"
DPS_BATTERY = "battery_percentage"
DPS_TEMP_CORRECTION = "temp_correction"
DPS_FROST = "frost"

# Light: Tuya value ranges
TUYA_BRIGHTNESS_MIN = 10
TUYA_BRIGHTNESS_MAX = 1000
TUYA_COLOUR_TEMP_MIN = 0
TUYA_COLOUR_TEMP_MAX = 1000

# HA colour temp range (kelvin)
HA_COLOUR_TEMP_MIN_KELVIN = 2000  # warmest (~500 mireds)
HA_COLOUR_TEMP_MAX_KELVIN = 6536  # coldest (~153 mireds)

# Extension socket / power strip DPS codes
DPS_CHILD_LOCK = "child_lock"
DPS_CUR_CURRENT = "cur_current"
DPS_CUR_VOLTAGE = "cur_voltage"
DPS_CUR_POWER = "cur_power"
DPS_TOTAL_ENERGY = "total_forward_energy"
DPS_FAULT = "fault"
DPS_OVERVOLTAGE_ALARM = "overvoltage_alarm"
DPS_OVERCURRENT_ALARM = "overcurrent_alarm"
DPS_OVERTEMP_ALARM = "overtemperature_alarm"
DPS_COUNTDOWN_PREFIX = "countdown_"   # countdown_1, countdown_2, …
DPS_RELAY_STATUS = "relay_status"

# Tuya fault bitmap masks (bitwise flags in the 'fault' DPS)
FAULT_OVERVOLTAGE_BIT = 0x01
FAULT_OVERCURRENT_BIT = 0x02
FAULT_OVERTEMP_BIT    = 0x04
FAULT_LEAKAGE_BIT     = 0x08

# Known product IDs → device type (fallback when schema detection fails)
KNOWN_PRODUCT_TYPES: dict[str, str] = {
    "pq860vo9ib50jhud": "switch",
    # Add more as discovered
}
