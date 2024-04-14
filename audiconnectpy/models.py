"""Definition class."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
import logging
from typing import Any

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

        vehicle_data = self.data
        if vehicle_data is None:
            return ExtendedDict(attrs)

        for key, raw_data in vehicle_data.items():
            match key:
                case "access":
                    data = raw_data.get("accessStatus", {}).get("value", {})
                    windows_status = self.windows_status(
                        self.map_name_status(data.get("windows"))
                    )
                    doors_status = self.doors_status(
                        self.map_name_status(data.get("doors"))
                    )
                    attrs.update(
                        {
                            "overall_status": data.get("overallStatus"),
                            "doors_lock_status": data.get("doorLockStatus"),
                            "last_update_time": data.get("carCapturedTimestamp"),
                            **windows_status,
                            **doors_status,
                        }
                    )
                case "userCapabilities":
                    capabilities = raw_data.get("capabilitiesStatus", {}).get(
                        "value", {}
                    )
                    caps = [capability.get("id") for capability in capabilities]
                    attrs.update({"capabilities": caps})
                case "fuelStatus":
                    data = raw_data.get("rangeStatus", {}).get("value", {})
                    primary_engine = data.get("primaryEngine", {})
                    secondary_engine = data.get("secondaryEngine", {})
                    attrs.update(
                        {
                            "primary_engine_type": primary_engine.get("type"),
                            "tank_level_in_percentage": primary_engine.get(
                                "currentFuelLevel_pct"
                            ),
                            "primary_engine_range": primary_engine.get(
                                "remainingRange_km"
                            ),
                        }
                    )
                    if secondary_engine:
                        attrs.update(
                            {
                                "secondary_engine_type": secondary_engine.get("type"),
                                "secondary_engine_range": secondary_engine.get(
                                    "remainingRange_km"
                                ),
                            }
                        )
                case "measurements":
                    range = raw_data.get("rangeStatus", {}).get("value", {})
                    # fuel_level = raw_data.get("fuelLevelStatus", {}).get("value", {})
                    odometer = raw_data.get("odometerStatus", {}).get("value", {})
                    attrs.update(
                        {
                            "measure_mileage": odometer.get("odometer"),
                            "gasoline_range": range.get("gasolineRange"),
                        }
                    )
                case "oiLevel":
                    data = raw_data.get("oilLevelStatus", {}).get("value", {})
                    attrs.update({"oil_level_status": data.get("value")})
                case "vehicleLights":
                    data = (
                        raw_data.get("lightsStatus", {})
                        .get("value", {})
                        .get("lights", [])
                    )
                    for light in data:
                        attrs.update(
                            {
                                f"lights_{light.get('name')}_turn_off": light.get(
                                    "status"
                                )
                                == "Off"
                            }
                        )
                case "vehicleHealthInspection":
                    data = raw_data.get("maintenanceStatus", {}).get("value", {})
                    attrs.update(
                        {
                            "maintenance_interval_time_to_inspection": data.get(
                                "inspectionDue_days"
                            ),
                            "maintenance_interval_distance_to_inspection": data.get(
                                "inspectionDue_km"
                            ),
                            "total_range": data.get("mileage_km"),
                            "maintenance_interval_distance_to_oil_change": data.get(
                                "oilServiceDue_km"
                            ),
                            "maintenance_interval_time_to_oil_change": data.get(
                                "oilServiceDue_days"
                            ),
                        }
                    )
                case "vehicleHealthWarnings":
                    data = raw_data.get("warningLights", {}).get("value", {})
        return attrs

    @staticmethod
    def tyres_status(attrs: ExtendedDict) -> ExtendedDict:
        metadatas = ExtendedDict({})
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

    @staticmethod
    def windows_status(attrs: ExtendedDict) -> ExtendedDict:
        # Windows open status
        metadatas = ExtendedDict({})
        left_open = "closed" not in attrs.get("frontLeft", [])
        left_rear_open = "closed" not in attrs.get("rearLeft", [])
        right_open = "closed" not in attrs.get("frontRight", [])
        right_rear_open = "closed" not in attrs.get("rearRight", [])
        any_window_open = (
            left_open and left_rear_open and right_open and right_rear_open
        )
        metadatas.update(
            {
                "open_left_front_window": left_open,
                "open_left_rear_window": left_rear_open,
                "open_right_front_window": right_open,
                "open_right_rear_window": right_rear_open,
                "open_any_window": any_window_open,
            }
        )

        if "unsupported" not in attrs.get("roofCover"):
            metadatas.update(
                {"open_roof_cover": "closed" not in attrs.get("roofCover", [])}
            )
        if "unsupported" not in attrs.get("sunRoof"):
            metadatas.update(
                {"open_sun_roof": "closed" not in attrs.get("sunRoof", [])}
            )

        return metadatas

    @staticmethod
    def doors_status(attrs: ExtendedDict) -> ExtendedDict:
        # Doors lock status
        metadatas = ExtendedDict({})
        left_unlock = "locked" not in attrs.get("frontLeft", [])
        left_rear_unlock = "locked" not in attrs.get("rearLeft", [])
        right_unlock = "locked" not in attrs.get("frontRight", [])
        right_rear_unlock = "locked" not in attrs.get("rearRight", [])
        trunk_unlock = "locked" not in attrs.get("trunk", [])
        unlock_any_door = (
            left_unlock and left_rear_unlock and right_unlock and right_rear_unlock
        )
        metadatas.update(
            {
                "lock_left_front_door": left_unlock,
                "lock_left_rear_door": left_rear_unlock,
                "lock_right_front_door": right_unlock,
                "lock_right_rear_door": right_rear_unlock,
                "lock_trunk": trunk_unlock,
                "lock_any_door": unlock_any_door,
                "lock_doors_trunk": True if unlock_any_door and trunk_unlock else False,
            }
        )

        # Doors open status
        left_open = "closed" not in attrs.get("frontLeft", [])
        left_rear_open = "closed" not in attrs.get("rearLeft", [])
        right_open = "closed" not in attrs.get("frontRight", [])
        right_rear_open = "closed" not in attrs.get("rearRight", [])
        trunk_open = "closed" not in attrs.get("trunk", [])
        bonnet_open = "closed" not in attrs.get("bonnet", [])
        open_any_door = (
            left_open
            and left_rear_open
            and right_open
            and right_rear_open
            and trunk_open
            and bonnet_open
        )

        metadatas.update(
            {
                "open_left_front_door": left_open,
                "open_left_rear_door": left_rear_open,
                "open_right_front_door": right_open,
                "open_right_rear_door": right_rear_open,
                "open_trunk": trunk_open,
                "open_bonnet": bonnet_open,
                "open_any_door": open_any_door,
            }
        )

        return metadatas

    @staticmethod
    def map_name_status(array: dict[str, Any]) -> dict[str, Any]:
        """Convert name/status to dictionary."""
        return {item.get("name"): item.get("status") for item in array}


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
            # chargingStatusData
            "charging_state": charging.getr("chargingState.content"),
            "actual_charge_rate": charging.getr("actualChargeRate.content"),
            "actual_charge_rate_unit": charging.getr("chargeRateUnit.content"),
            "charging_power": charging.getr("chargingPower.content"),
            "charging_mode": charging.getr("chargingMode.content"),
            "energy_flow": charging.getr("energyFlow.content"),
            # cruisingRangeStatusData
            "primary_engine_type": cruising.getr("engineTypeFirstEngine.content"),
            "secondary_engine_type": cruising.getr("engineTypeSecondEngine.content"),
            "hybrid_range": cruising.getr("hybridRange.content"),
            "primary_engine_range": cruising.getr("primaryEngineRange.content"),
            "secondary_engine_range": cruising.getr("secondaryEngineRange.content"),
            # PlugStatusData
            "plug_state": status.getr("plugStatusData.plugState.content"),
            "plug_lock": status.getr("plugStatusData.lockState.content"),
            # ledStatusData
            "led_color": status.getr("ledStatusData.ledColor.content"),
            "led_state": status.getr("ledStatusData.ledState.content"),
            # BatteryStatusData
            "state_of_charge": status.getr("batteryStatusData.stateOfCharge.content"),
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
            "climatisation_heater_src": settings.getr("heaterSource.content"),
            "climatisation_target_temp": settings.getr("targetTemperature.content"),
            "climatisation_state": status.getr(
                "climatisationStatusData.climatisationState.content"
            ),
            "climatisation_remaining_time": status.getr(
                "climatisationStatusData.remainingClimatisationTime.content"
            ),
            "outdoor_temperature": status.getr(
                "temperatureStatusData.outdoorTemperature.content"
            ),
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
        return self.data.get("data") is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        attrs = {
            "position": ExtendedDict(
                {
                    "latitude": self.data.getr("data.lat", 0),
                    "longitude": self.data.getr("data.lon", 0),
                    "parktime": self.data.getr("data.carCapturedTimestamp"),
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


@dataclass
class ClimaterTimerDataResponse:
    """Climater timer class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return (
            self.data.getr("timer.timersAndProfiles") is not None
            or self.data.getr("timer.status") is not None
        )

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        profiles = self.data.getr("timer.timersAndProfiles", {})
        # status = self.data.getr("climater_timer.timer.status", {})
        attrs = {
            "climater_timer_profil_list": profiles.getr(
                "timerProfileList.timerProfile"
            ),
        }
        return ExtendedDict(attrs)


@dataclass
class HonkFlashDataResponse:
    """Climater timer class."""

    data: ExtendedDict

    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.data.getr("honkAndFlashConfiguration") is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        settings = self.data.getr("honkAndFlashConfiguration", {})
        # status = self.data.getr("climater_timer.timer.status", {})
        attrs = {
            "honkflash_default_duration": settings.getr("defaultServiceDuration"),
            "honkflash_max_duration": settings.getr("maximumServiceDuration"),
            "honkflash_honk_forbidden": settings.getr("honkForbidden"),
            "honkflash_flash_forbidden": settings.getr("flashForbidden"),
            "honkflash_max_distance": settings.getr("maximumDistanceToVehicle"),
            "honkflash_distance_restriction": settings.getr(
                "distanceRestrictionForSignal"
            ),
        }
        return ExtendedDict(attrs)
