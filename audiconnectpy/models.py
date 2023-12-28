"""Definition class."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime as dt

from .helpers import ExtendedDict

_LOGGER = logging.getLogger(__name__)


class Globals:
    """Global variables."""

    def __init__(self, unit: str) -> None:
        """Initilaze."""
        global UNIT_SYSTEM  # pylint: disable=global-variable-undefined
        UNIT_SYSTEM = f"{unit}"  # type: ignore


class VehicleDataResponse:
    """Status class."""

    IDS = {
        "0x0": "unknown",
        "0x0101010001": "utc_time",
        "0x0101010002": "utc_time_and_kilometer_status",
        "0x0202": "active_instrument_cluster_warning",
        "0x0203010001": "maintenance_interval_distance_to_oil_change",
        "0x0203010002": "maintenance_interval_time_to_oil_change",
        "0x0203010003": "maintenance_interval_distance_to_inspection",
        "0x0203010004": "maintenance_interval_time_to_inspection",
        "0x0203010005": "warning_oil_change",
        "0x0203010006": "maintenance_interval_alarm_inspection",
        "0x0203010007": "maintenance_interval_monthly_mileage",
        "0x0204040001": "oil_level_amount_in_liters",
        "0x0204040002": "oil_level_minimum_warning",
        "0x0204040003": "oil_level_dipsticks_percentage",
        "0x0204040004": "oil_display",
        "0x0204040005": "oil_level_valid",
        "0x0204040006": "oil_level_percentage",
        "0x02040C0001": "adblue_range",
        "0x02040C0002": "src_no_driveability",
        "0x0301010001": "light_status",
        "0x0301020001": "temperature_outside",
        "0x0301030001": "braking_status",
        "0x0301030002": "state_of_charge",
        "0x0301030003": "bem_ok",
        "0x0301030005": "total_range",
        "0x0301030006": "primary_range",
        "0x0301030007": "primary_drive",
        "0x0301030008": "secondary_range",
        "0x0301030009": "secondary_drive",
        "0x030103000A": "tank_level_in_percentage",
        "0x030103000D": "tank_level_error",
        "0x0301040001": "lock_state_left_front_door",
        "0x0301040002": "open_state_left_front_door",
        "0x0301040003": "safety_state_left_front_door",
        "0x0301040004": "lock_state_left_rear_door",
        "0x0301040005": "open_state_left_rear_door",
        "0x0301040006": "safety_state_left_rear_door",
        "0x0301040007": "lock_state_right_front_door",
        "0x0301040008": "open_state_right_front_door",
        "0x0301040009": "safety_state_right_front_door",
        "0x030104000A": "lock_state_right_rear_door",
        "0x030104000B": "open_state_right_rear_door",
        "0x030104000C": "safety_state_right_rear_door",
        "0x030104000D": "lock_state_trunk_lid",
        "0x030104000E": "open_state_trunk_lid",
        "0x030104000F": "safety_state_trunk_lid",
        "0x0301040010": "lock_state_hood",
        "0x0301040011": "open_state_hood",
        "0x0301040012": "safety_state_hood",
        "0x0301050001": "state_left_front_window",
        "0x0301050002": "position_left_front_window",
        "0x0301050003": "state_left_rear_window",
        "0x0301050004": "position_left_rear_window",
        "0x0301050005": "state_right_front_window",
        "0x0301050006": "position_right_front_window",
        "0x0301050007": "state_right_rear_window",
        "0x0301050008": "position_right_rear_window",
        "0x0301050009": "state_deck",
        "0x030105000A": "position_deck",
        "0x030105000B": "state_sun_roof_motor_cover",
        "0x030105000C": "position_sun_roof_motor_cover",
        "0x030105000D": "state_sun_roof_rear_motor_cover_3",
        "0x030105000E": "position_sun_roof_rear_motor_cover_3",
        "0x030105000F": "state_service_flap",
        "0x0301050011": "state_spoiler",
        "0x0301050012": "position_spoiler",
        "0x0301060001": "tyre_pressure_left_front_current_value",
        "0x0301060002": "tyre_pressure_left_front_desired_value",
        "0x0301060003": "tyre_pressure_left_rear_current_value",
        "0x0301060004": "tyre_pressure_left_rear_desired_value",
        "0x0301060005": "tyre_pressure_right_front_current_value",
        "0x0301060006": "tyre_pressure_right_front_desired_value",
        "0x0301060007": "tyre_pressure_right_rear_current_value",
        "0x0301060008": "tyre_pressure_right_rear_desired_value",
        "0x0301060009": "tyre_pressure_spare_tyre_current_value",
        "0x030106000A": "tyre_pressure_spare_tyre_desired_value",
        "0x030106000B": "tyre_pressure_left_front_tyre_difference",
        "0x030106000C": "tyre_pressure_left_rear_tyre_difference",
        "0x030106000D": "tyre_pressure_right_front_tyre_difference",
        "0x030106000E": "tyre_pressure_right_rear_tyre_difference",
        "0x030106000F": "tyre_pressure_spare_tyre_difference",
    }

    def __init__(self, data: ExtendedDict, has_pin: bool = False) -> None:
        """Initialize."""
        self.data = data
        self.has_pin = has_pin
        self.measure_time = None
        self.send_time = None
        self.send_time_utc = None
        self.measure_mileage = None
        self.send_mileage = None
        self._vehicle_data = self._get_attributes()

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.attributes is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        return self._vehicle_data

    def _get_attributes(self) -> ExtendedDict:
        attrs = ExtendedDict({"last_access": dt.now()})

        default = self.data.getr("CurrentVehicleDataByRequestResponse.vehicleData.data")
        vehicle_data = self.data.getr(
            "StoredVehicleDataResponse.vehicleData.data", default
        )
        if vehicle_data is None:
            return ExtendedDict(attrs)

        for raw_data in vehicle_data:
            for raw_field in raw_data.get("field", {}):
                ids = raw_field.get("id")
                value = raw_field.get("value")
                unit = raw_field.get("unit")
                if ids == "0x0101010001":
                    self.measure_time = raw_field.get("tsCarCaptured")
                    self.send_time = raw_field.get("tsCarSent")
                    self.send_time_utc = raw_field.get("tsCarSentUtc")
                    self.measure_mileage = raw_field.get("milCarCaptured")
                    self.send_mileage = raw_field.get("milCarSent")
                    attrs.update({"last_update_time": self.send_time_utc})

                if identity := self.IDS.get(ids):
                    try:
                        attrs.update({identity: int(value)})
                    except Exception:  # pylint: disable=broad-except
                        try:
                            attrs.update({identity: float(value)})
                        except Exception:  # pylint: disable=broad-except
                            attrs.update({identity: value})

                    if UNIT_SYSTEM == "imperial" and unit == "km":  # type: ignore
                        attrs[identity] = round(attrs[identity] * 0.621371, 2)

                else:
                    _LOGGER.error("%s not found", ids)

        # Append meta sensors
        attrs.update(self._metadatas(attrs))

        return attrs

    @staticmethod
    def _metadatas(attrs: ExtendedDict) -> ExtendedDict:
        metadatas = ExtendedDict({})

        # Windows open status
        left_check: int | None = attrs.get("state_left_front_window")
        left_rear_check: int | None = attrs.get("state_left_rear_window")
        right_check: int | None = attrs.get("state_right_front_window")
        right_rear_check: int | None = attrs.get("state_right_rear_window")
        if None not in [left_check, left_rear_check, right_check, right_rear_check]:
            any_window_open = (
                left_check != 3
                and left_rear_check != 3
                and right_check != 3
                and right_rear_check != 3
            )
            metadatas.update({"any_window_open": any_window_open})

        # Doors lock status
        left_check = attrs.get("lock_state_left_front_door")
        left_rear_check = attrs.get("lock_state_left_rear_door")
        right_check = attrs.get("lock_state_right_front_door")
        right_rear_check = attrs.get("lock_state_right_rear_door")
        trunk_unlocked = attrs.get("lock_state_trunk_lid") != 2
        if b_any_door_unlocked := (
            None not in [left_check, left_rear_check, right_check, right_rear_check]
        ):
            any_door_unlocked = (
                left_check != 2
                and left_rear_check != 2
                and right_check != 2
                and right_rear_check != 2
            )
            metadatas.update({"any_door_unlocked": any_door_unlocked})

        # Doors open status
        left_check = attrs.get("open_state_left_front_door")
        left_rear_check = attrs.get("open_state_left_rear_door")
        right_check = attrs.get("open_state_right_front_door")
        right_rear_check = attrs.get("open_state_right_rear_door")
        trunk_open = attrs.get("open_state_trunk_lid") != 3
        if b_any_door_open := (
            None not in [left_check, left_rear_check, right_check, right_rear_check]
        ):
            any_door_open = (
                left_check != 3
                and left_rear_check != 3
                and right_check != 3
                and right_rear_check != 3
            )
            metadatas.update({"any_door_open": any_door_open})

        # Door trunk status
        if b_any_door_open and b_any_door_unlocked and trunk_open and trunk_unlocked:
            if any_door_open and trunk_open:
                metadatas.update({"doors_trunk_status": "Open"})
            elif any_door_unlocked and trunk_unlocked:
                metadatas.update({"doors_trunk_status": "Closed"})
            else:
                metadatas.update({"doors_trunk_status": "Locked"})

        # Tyre pressure status
        left_check = attrs.get("tyre_pressure_left_front_tyre_difference")
        left_rear_check = attrs.get("tyre_pressure_left_rear_tyre_difference")
        right_check = attrs.get("tyre_pressure_right_front_tyre_difference")
        right_rear_check = attrs.get("tyre_pressure_right_rear_tyre_difference")
        spare_check = attrs.get("tyre_pressure_spare_tyre_difference")
        if None not in [
            left_check,
            left_rear_check,
            right_check,
            right_rear_check,
            spare_check,
        ]:
            any_tyre_pressure = (
                left_check != 1
                and left_rear_check != 1
                and right_check != 1
                and right_rear_check != 1
                and spare_check != 1
            )
            metadatas.update({"any_tyre_problem": any_tyre_pressure})

        return metadatas


@dataclass
class PreheaterDataResponse:
    """Preheater class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.data.getr("statusResponse.climatisationStateReport") is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        report: ExtendedDict = self.data.getr(
            "statusResponse.climatisationStateReport", {}
        )
        attrs = {
            "preheater_state": report,
            "preheater_active": report.get("climatisationState"),
            "preheater_duration": report.get("climatisationDuration"),
            "preheater_remaining": report.get("remainingClimateTime"),
        }
        return ExtendedDict(attrs)


@dataclass
class ChargerDataResponse:
    """Charger class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return (
            self.data.getr("charger.settings") is not None
            or self.data.getr("charger.status") is not None
        )

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        settings = self.data.getr("charger.settings", {})
        status = self.data.getr("charger.status", {})
        charging = status.getr("chargingStatusData", {})
        cruising = status.getr("cruisingRangeStatusData", {})
        attrs = {
            "max_charge_current": settings.getr("maxChargeCurrent.content"),
            "charging_state": charging.getr("chargingState.content"),
            "actual_charge_rate": charging.getr("actualChargeRate.content"),
            "actual_charge_rate_unit": charging.getr("chargeRateUnit.content"),
            "charging_power": charging.getr("chargingPower.content"),
            "charging_mode": charging.getr("chargingMode.content"),
            "energy_flow": charging.getr("energyFlow.content"),
            "primary_engine_type": cruising.getr("engineTypeFirstEngine.content"),
            "secondary_engine_type": cruising.getr("engineTypeSecondEngine.content"),
            "hybrid_range": cruising.getr("hybridRange.content"),
            "primary_engine_range": cruising.getr("primaryEngineRange.content"),
            "secondary_engine_range": cruising.getr("secondaryEngineRange.content"),
            "state_of_charge": status.getr("batteryStatusData.stateOfCharge.content"),
            "plug_state": status.getr("plugStatusData.plugState.content"),
            "plug_lock": status.getr("plugStatusData.lockState.content"),
            "remaining_charging_time": status.getr(
                "batteryStatusData.remainingChargingTime.content"
            ),
        }
        return ExtendedDict(attrs)


@dataclass
class ClimaterDataResponse:
    """Climater class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return (
            self.data.getr("climater.settings") is not None
            or self.data.getr("climater.status") is not None
        )

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        settings = self.data.getr("climater.settings", {})
        status = self.data.getr("climater.status", {})
        attrs = {
            "climatisation_state": status.getr(
                "climatisationStatusData.climatisationState.content"
            ),
            "outdoor_temperature": status.getr(
                "temperatureStatusData.outdoorTemperature.content"
            ),
            "climatisation_heater_src": settings.getr("heaterSource.content"),
            "climatisation_target_temp": settings.getr("targetTemperature.content"),
        }
        return ExtendedDict(attrs)


@dataclass
class DestinationDataResponse:
    """Destination."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.attributes is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        attrs = self.data
        return ExtendedDict(attrs)


@dataclass
class HistoryDataResponse:
    """Destination."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.attributes is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        attrs = self.data
        return ExtendedDict(attrs)


@dataclass
class UsersDataResponse:
    """Destination."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.attributes is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        attrs = self.data
        return ExtendedDict(attrs)


@dataclass
class PositionDataResponse:
    """Position class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.data.getr("findCarResponse.Position") is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        coordinate = self.data.getr("findCarResponse.Position.carCoordinate", {})
        timestamp = self.data.getr("findCarResponse.Position.timestampCarSentUTC")
        attrs = {
            "position": ExtendedDict(
                {
                    "latitude": coordinate.get("latitude", 0) / 1000000,
                    "longitude": coordinate.get("longitude", 0) / 1000000,
                    "timestamp": timestamp,
                    "parktime": self.data.getr(
                        "findCarResponse.parkingTimeUTC", timestamp
                    ),
                }
            )
        }
        return ExtendedDict(attrs)


@dataclass
class TripDataResponse:
    """Trip class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.data.get("tripID") is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        attrs = {
            "tripID": self.data.get("tripID"),
            "averageElectricEngineConsumption": (
                float(self.data.get("averageElectricEngineConsumption", 0)) / 10
            ),
            "averageFuelConsumption": (
                float(self.data.get("averageFuelConsumption", 0)) / 10
            ),
            "averageSpeed": int(self.data.get("averageSpeed", 0)),
            "mileage": int(self.data.get("mileage", 0)),
            "startMileage": int(self.data.get("startMileage", 0)),
            "traveltime": int(self.data.get("traveltime", 0)),
            "timestamp": self.data.get("timestamp"),
            "overallMileage": int(self.data.get("overallMileage", 0)),
        }
        return ExtendedDict(attrs)
