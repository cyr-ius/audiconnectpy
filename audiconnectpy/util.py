"""Helper functions."""
from __future__ import annotations

import functools
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import reduce
from typing import Any, Callable

from .exceptions import TimeoutExceededError

_LOGGER = logging.getLogger(__name__)


@dataclass
class FieldType:
    """Field type."""

    name: str | None = None
    attr: str | None = None
    sensor_type: str | None = None
    unit_of_measurement: str | None = None
    evaluation: Callable[[Any], Any] | None = None
    device_class: str | None = None
    icon: str | None = None
    turn_mode: str | None = None


class Identities(Enum):
    """IDS Audi."""

    # Fields
    # pylint: disable=unnecessary-lambda
    UTC_TIME_AND_KILOMETER_STATUS = FieldType(
        attr="mileage",
        sensor_type="sensor",
        icon="mdi:speedometer",
        unit_of_measurement="km",
        evaluation=lambda x: int(x),
        device_class="distance",
    )
    MAINTENANCE_INTERVAL_DISTANCE_TO_OIL_CHANGE = FieldType(
        attr="oil_change_distance",
        sensor_type="sensor",
        evaluation=lambda x: abs(int(x)),
        icon="mdi:oil",
        unit_of_measurement="km",
        device_class="distance",
    )
    MAINTENANCE_INTERVAL_TIME_TO_OIL_CHANGE = FieldType(
        attr="oil_change_time",
        sensor_type="sensor",
        evaluation=lambda x: abs(int(x)),
        icon="mdi:oil",
        unit_of_measurement="d",
        device_class="duration",
    )
    MAINTENANCE_INTERVAL_DISTANCE_TO_INSPECTION = FieldType(
        attr="service_inspection_distance",
        sensor_type="sensor",
        icon="mdi:room-service-outline",
        unit_of_measurement="km",
        evaluation=lambda x: abs(int(x)),
        device_class="distance",
    )
    MAINTENANCE_INTERVAL_TIME_TO_INSPECTION = FieldType(
        attr="service_inspection_time",
        sensor_type="sensor",
        icon="mdi:room-service-outline",
        unit_of_measurement="d",
        evaluation=lambda x: abs(int(x)),
        device_class="duration",
    )
    WARNING_OIL_CHANGE = FieldType(
        attr="oil_change",
        sensor_type="binary_sensor",
        evaluation=lambda x: x == "1",
        icon="mdi:oil",
    )
    OIL_LEVEL_DIPSTICKS_PERCENTAGE = FieldType(
        attr="oil_level",
        sensor_type="sensor",
        evaluation=lambda x: float(x),
        icon="mdi:oil",
        unit_of_measurement="%",
    )
    OIL_DISPLAY = FieldType(
        attr="oil_display",
        sensor_type="binary_sensor",
        evaluation=lambda x: x == "1",
        icon="mdi:oil",
    )
    OIL_LEVEL_VALID = FieldType(
        attr="oil_level_valid",
        sensor_type="binary_sensor",
        evaluation=lambda x: x == "1",
        icon="mdi:oil",
    )
    ADBLUE_RANGE = FieldType(
        attr="adblue_range",
        sensor_type="sensor",
        evaluation=lambda x: int(x),
    )
    LIGHT_STATUS = FieldType(
        attr="parking_light",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="safety",
        icon="mdi:lightbulb",
    )
    TEMPERATURE_OUTSIDE = FieldType(
        attr="temperature_outside", sensor_type="sensor", device_class="temperature"
    )
    BRAKING_STATUS = FieldType(
        attr="braking_status",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
    )
    BEM_OK = FieldType(
        attr="bem_status",
        sensor_type="sensor",
        evaluation=lambda x: int(x),
        device_class="problem",
    )
    TOTAL_RANGE = FieldType(
        attr="range",
        sensor_type="sensor",
        evaluation=lambda x: int(x),
        icon="mdi:gas-station",
        unit_of_measurement="km",
        device_class="distance",
    )
    TANK_LEVEL_IN_PERCENTAGE = FieldType(
        attr="tank_level",
        sensor_type="sensor",
        evaluation=lambda x: int(x),
        icon="mdi:gas-station",
        unit_of_measurement="%",
    )
    LOCK_STATE_LEFT_FRONT_DOOR = FieldType(
        attr="unlock_left_front_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="lock",
    )
    LOCK_STATE_LEFT_REAR_DOOR = FieldType(
        attr="unlock_left_rear_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="lock",
    )
    LOCK_STATE_RIGHT_FRONT_DOOR = FieldType(
        attr="unlock_right_front_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="lock",
    )
    LOCK_STATE_RIGHT_REAR_DOOR = FieldType(
        attr="unlock_right_rear_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="lock",
    )
    OPEN_STATE_LEFT_FRONT_DOOR = FieldType(
        attr="open_left_front_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="door",
    )
    OPEN_STATE_LEFT_REAR_DOOR = FieldType(
        attr="open_left_rear_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="door",
    )
    OPEN_STATE_RIGHT_FRONT_DOOR = FieldType(
        attr="open_right_front_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="door",
    )
    OPEN_STATE_RIGHT_REAR_DOOR = FieldType(
        attr="open_right_rear_door",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="door",
    )
    LOCK_STATE_TRUNK_LID = FieldType(
        attr="trunk_unlocked",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="lock",
    )
    OPEN_STATE_TRUNK_LID = FieldType(
        attr="trunk_open",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="door",
    )
    LOCK_STATE_HOOD = FieldType(
        attr="hood_unlocked",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "2",
        device_class="lock",
    )
    OPEN_STATE_HOOD = FieldType(
        attr="hood_open",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="door",
    )
    STATE_LEFT_FRONT_WINDOW = FieldType(
        attr="open_left_front_windows",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="window",
    )
    STATE_LEFT_REAR_WINDOW = FieldType(
        attr="open_left_rear_windows",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="window",
    )
    STATE_RIGHT_FRONT_WINDOW = FieldType(
        attr="open_right_front_windows",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="window",
    )
    STATE_RIGHT_REAR_WINDOW = FieldType(
        attr="open_right_rear_windows",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="window",
    )
    STATE_SUN_ROOF_MOTOR_COVER = FieldType(
        attr="sun_roof",
        sensor_type="binary_sensor",
        evaluation=lambda x: x == "2",
        device_class="cover",
    )
    STATE_SPOILER = FieldType(
        attr="spoiler",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "3",
        device_class="lock",
    )
    TYRE_PRESSURE_LEFT_FRONT_TYRE_DIFFERENCE = FieldType(
        attr="tyre_pressure_left_front",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "1",
        device_class="problem",
    )
    TYRE_PRESSURE_LEFT_REAR_TYRE_DIFFERENCE = FieldType(
        attr="tyre_pressure_left_rear",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "1",
        device_class="problem",
    )
    TYRE_PRESSURE_RIGHT_FRONT_TYRE_DIFFERENCE = FieldType(
        attr="tyre_pressure_right_front",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "1",
        device_class="problem",
    )
    TYRE_PRESSURE_RIGHT_REAR_TYRE_DIFFERENCE = FieldType(
        attr="tyre_pressure_right_rear",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "1",
        device_class="problem",
    )
    TYRE_PRESSURE_SPARE_TYRE_DIFFERENCE = FieldType(
        attr="tyre_pressure_spare",
        sensor_type="binary_sensor",
        evaluation=lambda x: x != "1",
        device_class="problem",
    )

    # Preheater
    PREHEATER_STATE = FieldType(
        attr="preheater_state",
        evaluation=lambda x: x is not None,
        sensor_type="switch",
        turn_mode="async_switch_pre_heating",
    )
    PREHEATER_ACTIVE = FieldType(
        attr="preheater_active",
        evaluation=lambda x: x != "off",
        sensor_type="switch",
        turn_mode="async_switch_pre_heating",
    )
    PREHEATER_DURATION = FieldType(
        attr="preheater_duration",
        evaluation=lambda x: int(x),
        sensor_type="sensor",
        icon="mdi:clock",
        unit_of_measurement="Min",
    )
    PREHEATER_REMAINING = FieldType(
        attr="preheater_remaining",
        evaluation=lambda x: int(x),
        sensor_type="sensor",
        icon="mdi:clock",
        unit_of_measurement="Min",
    )

    # Charger
    MAX_CHARGE_CURRENT = FieldType(
        attr="max_charge_current",
        sensor_type="sensor",
        icon="mdi:current-ac",
        unit_of_measurement="A",
    )
    CHARGING_STATE = FieldType(
        attr="charging_state",
        sensor_type="sensor",
        icon="mdi:car-battery",
    )
    ACTUAL_CHARGE_RATE = FieldType(
        attr="actual_charge_rate",
        sensor_type="sensor",
        icon="mdi:electron-framework",
        evaluation=lambda x: float(x) / 10,
    )
    ACTUAL_CHARGE_RATE_UNIT = FieldType(
        attr="actual_charge_rate_unit",
        sensor_type="sensor",
        evaluation=lambda x: x.replace("_per_", "/"),
    )
    CHARGING_POWER = FieldType(
        attr="charging_power",
        sensor_type="sensor",
        icon="mdi:flash",
        unit_of_measurement="kW",
        evaluation=lambda x: int(x) / 1000,
        device_class="power",
    )
    CHARGING_MODE = FieldType(
        attr="charging_mode",
        sensor_type="switch",
        turn_mode="async_switch_charger",
    )
    ENERGY_FLOW = FieldType(
        attr="energy_flow",
        sensor_type="sensor",
    )
    PRIMARY_ENGINE_TYPE = FieldType(
        attr="primary_engine_type",
        sensor_type="sensor",
        icon="mdi:engine",
    )
    SECONDARY_ENGINE_TYPE = FieldType(
        attr="secondary_engine_type",
        sensor_type="sensor",
        icon="mdi:engine",
    )
    HYBRID_RANGE = FieldType(
        attr="hybrid_range",
        sensor_type="sensor",
    )
    PRIMARY_ENGINE_RANGE = FieldType(
        attr="primary_engine_range",
        sensor_type="sensor",
        icon="mdi:gas-station-outline",
        unit_of_measurement="km",
    )
    SECONDARY_ENGINE_RANGE = FieldType(
        attr="secondary_engine_range",
        sensor_type="sensor",
        icon="mdi:gas-station-outline",
        unit_of_measurement="km",
    )
    STATE_OF_CHARGE = FieldType(
        attr="state_of_charge",
        sensor_type="sensor",
        icon="mdi:ev-station",
        unit_of_measurement="%",
        device_class="power_factor",
    )
    PLUG_STATE = FieldType(
        attr="plug_state",
        sensor_type="sensor",
        icon="mdi:power-plug",
    )
    PLUG_LOCK = FieldType(
        attr="plug_lock",
        sensor_type="sensor",
        icon="mdi:power-plug",
    )
    REMAINING_CHARGING_TIME = FieldType(
        attr="remaining_charging_time",
        sensor_type="sensor",
        icon="mdi:battery-charging",
        evaluation=lambda x: "n/a"
        if int(x) == 65535
        else "{r[0]:02d}:{r[1]:02d}".format(r=divmod(x, 60)),
    )

    # Climater
    CLIMATISATION_STATE = FieldType(
        attr="climatisation_state",
        icon="mdi:air-conditioner",
        sensor_type="switch",
        turn_mode="async_switch_climater",
    )
    CLIMATISATION_TARGET_TEMP = FieldType(
        attr="climatisation_target_temperature",
        icon="mdi:temperature-celsius",
        sensor_type="sensor",
        unit_of_measurement="°C",
        evaluation=lambda x: round(float(x) / 10 - 273, 1),
        device_class="temperature",
    )
    CLIMATISATION_HEATER_SRC = FieldType(
        attr="climatisation_heater_source",
        icon="mdi:air-conditioner",
        sensor_type="sensor",
    )
    OUTDOOR_TEMPERATURE = FieldType(
        attr="outdoor_temperature",
        sensor_type="sensor",
        icon="mdi:temperature-celsius",
        unit_of_measurement="°C",
        evaluation=lambda x: round(float(x) / 10 - 273, 1),
        device_class="temperature",
    )

    # Position
    POSITION = FieldType(
        attr="position",
        sensor_type="device_tracker",
    )

    # Trip
    TRIP = FieldType(
        attr="trip",
        sensor_type="sensor",
    )

    # Meta sensors
    ANY_WINDOW_OPEN = FieldType(
        attr="any_window_open", sensor_type="binary_sensor", device_class="window"
    )
    ANY_DOOR_UNLOCKED = FieldType(
        attr="any_door_unlocked",
        sensor_type="lock",
        device_class="lock",
        turn_mode="async_switch_lock",
    )
    ANY_DOOR_OPEN = FieldType(
        attr="any_door_open", sensor_type="binary_sensor", device_class="door"
    )
    DOORS_TRUNK_STATUS = FieldType(
        attr="doors_trunk_status", sensor_type="sensor", icon="mdi:car-door"
    )
    LOCK_SUPPORTED = FieldType(attr="lock_supported", sensor_type="binary_sensor")
    ANY_TYRE_PRESSURE = FieldType(
        attr="any_tyre_pressure", sensor_type="binary_sensor", device_class="problem"
    )
    LAST_UPDATE_TIME = FieldType(
        attr="last_update_time",
        sensor_type="sensor",
        icon="mdi:update",
        device_class="timestamp",
    )
    SHORTTERM_RESET = FieldType(attr="shortterm_reset", sensor_type="sensor")
    SHORTTERM_CURRENT = FieldType(attr="shortterm_current", sensor_type="sensor")
    LONGTERM_RESET = FieldType(attr="longterm_reset", sensor_type="sensor")
    LONGTERM_CURRENT = FieldType(attr="longterm_current", sensor_type="sensor")
    # pylint: enable=unnecessary-lambda


class Globals:
    """Global variables."""

    def __init__(self, unit: str) -> None:
        """Initiliaze."""
        global UNIT_SYSTEM  # pylint: disable=global-variable-undefined
        UNIT_SYSTEM = f"{unit}"  # type: ignore


def get_attr(
    dictionary: dict[Any, dict[str, Any]], keys: str, default: str | None = None
) -> Any:
    """Return attribute value."""
    return reduce(
        lambda d, key: d.get(key, default) if isinstance(d, dict) else default,  # type: ignore
        keys.split("."),
        dictionary,
    )


def to_byte_array(hex_string: str) -> list[int]:
    """Return byte array."""
    result = []
    for i in range(0, len(hex_string), 2):
        result.append(int(hex_string[i : i + 2], 16))

    return result


def set_attr(
    identity: str, value: Any, unit: str | None = None
) -> dict[Any, dict[str, Any]]:
    """Check attribut in Identies class and return dictionnary.

    This returned dict contain attribut , type , device class, icon , unit
    and turn_mode (Function that performs an action)
    the evaluation method makes it possible to interpret the value returned
    by Audi Connect and to adapt it to an exploitable value
    """
    ids_type = getattr(Identities, identity, None)
    attribute = {}
    if ids_type:
        field_type = ids_type.value
        if field_type.evaluation and value:
            try:
                value = field_type.evaluation(value)
                if UNIT_SYSTEM == "imperial" and field_type.unit == "km":  # type: ignore
                    unit = "mi"
                    value = round(value * 0.621371, 2)
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error(error)

        attribute.update(
            {
                field_type.attr: {
                    "value": value,
                    "unit_of_measurement": field_type.unit_of_measurement
                    if unit is None
                    else unit,
                    "device_class": field_type.device_class,
                    "icon": field_type.icon,
                    "sensor_type": field_type.sensor_type,
                    "turn_mode": field_type.turn_mode,
                }
            }
        )
    return attribute


def jload(json_data: Any) -> Any:
    """Load json with error manage."""
    if not isinstance(json_data, dict):
        return json.loads(json_data)
    return json_data


def obj_parser(obj: dict[str, Any]) -> dict[str, Any]:
    """Parse datetime."""
    for key, val in obj.items():
        try:
            obj[key] = datetime.strptime(val, "%Y-%m-%dT%H:%M:%S%z")
        except (TypeError, ValueError):
            pass
    return obj


def json_loads(jsload: str | bytes) -> Any:
    """Json load."""
    return json.loads(jsload, object_hook=obj_parser)


def retry(
    exceptions: Any = Exception,
    tries: int = -1,
    delay: float = 0,
    max_delay: int | None = None,
    backoff: int = 1,
    jitter: int | tuple[int, int] = 0,
    logger: Any = _LOGGER,
) -> Callable[..., Any]:
    """Retry Decorator.

    :param exceptions: an exception or a tuple of exceptions to catch. default: Exception.
    :param tries: the maximum number of attempts. default: -1 (infinite).
    :param delay: initial delay between attempts. default: 0.
    :param max_delay: the maximum value of delay. default: None (no limit).
    :param backoff: multiplier applied to delay between attempts. default: 1 (no backoff).
    :param jitter: extra seconds added to delay between attempts. default: 0.
                   fixed if a number, random if a range tuple (min, max)
    :param logger: logger.warning(fmt, error, delay) will be called on failed attempts.
                   default: retry.logging_logger. if None, logging is disabled.
    :returns: the result of the f function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Add decorator."""

        @functools.wraps(func)
        async def newfn(*args: Any, **kwargs: Any) -> Any:
            """Load function."""
            _tries, _delay = tries, delay
            while _tries:
                try:
                    return await func(*args, **kwargs)
                except exceptions as error:  # pylint: disable=broad-except
                    _tries -= 1
                    if not _tries:
                        raise TimeoutExceededError(error) from error

                    if logger is not None:
                        logger.warning("%s, retrying in %s seconds...", error, _delay)

                    time.sleep(_delay)
                    _delay *= backoff

                    if isinstance(jitter, tuple):
                        _delay += random.uniform(*jitter)
                    else:
                        _delay += jitter

                    if max_delay is not None:
                        _delay = min(_delay, max_delay)

        return newfn

    return decorator
