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

    data: ExtendedDict
    
    @property
    def is_supported(self) -> bool:
        """Supported status."""
        return self.data.getr("fuelStatus.rangeStatus.value" is not None
        )

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        value = self.data.getr("fuelStatus.rangeStatus.value", {})
        attrs = {
            "total_range": value.get("totalRange_km"),
        }
        return ExtendedDict(attrs)

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
        return self.data.getr("data") is not None

    @property
    def attributes(self) -> ExtendedDict:
        """Attributes properties."""
        timestamp = self.data.getr("data.carCapturedTimestamp")
        attrs = {
            "position": ExtendedDict(
                {
                    "latitude": self.data.get("data.lat", 0),
                    "longitude": self.data.get("data.lon", 0),
                    "timestamp": timestamp,
                    "parktime": timestamp,
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
