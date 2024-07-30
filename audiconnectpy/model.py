"""Model class."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WrapSerializer,
)
from pydantic.alias_generators import to_camel
from pydantic_extra_types.coordinate import Latitude, Longitude
from typing_extensions import Annotated

from .helpers import doors_status, lights_status, window_heating_status, windows_status

TActived = Annotated[
    str, PlainSerializer(lambda x: x.lower() == "active", return_type=bool)
]
TCharging = Annotated[
    str, PlainSerializer(lambda x: x.lower() == "charging", return_type=bool)
]
TConnected = Annotated[
    str, PlainSerializer(lambda x: x.lower() == "connected", return_type=bool)
]
TDoorLocked = Annotated[list, WrapSerializer(doors_status, return_type=dict)]

TLocked = Annotated[
    str, PlainSerializer(lambda x: x.lower() == "locked", return_type=bool)
]
TWindowOpened = Annotated[list, WrapSerializer(windows_status, return_type=dict)]
TWindowHeating = Annotated[
    list, WrapSerializer(window_heating_status, return_type=dict)
]
TLights = Annotated[list, WrapSerializer(lights_status, return_type=dict)]


# SECTION
class Base(BaseModel):  # type: ignore
    """Vehicle."""

    model_config = ConfigDict(alias_generator=to_camel)


class UserCapabilities(Base):
    capabilities_status: list[Capability] | None = Field(
        validation_alias=AliasPath("capabilitiesStatus", "value")
    )


class Capability(Base):
    id: str
    user_disabling_allowed: bool
    expiration_date: datetime | None = None


# SECTION
class Access(Base):
    access_status: AccessStatus | None = Field(
        validation_alias=AliasPath("accessStatus", "value")
    )


class AccessStatus(Base):
    """Return accessStatus."""

    car_captured_timestamp: datetime
    overall_status: str | None = None
    door_lock_status: TLocked | None = None
    doors: TDoorLocked | None = None  # type: ignore
    windows: TWindowOpened | None = None  # type: ignore


# SECTION
class Charging(Base):
    battery_status: BatteryStatus | None = Field(
        default=None, validation_alias=AliasPath("batteryStatus", "value")
    )
    charging_status: ChargingStatus | None = Field(
        default=None, validation_alias=AliasPath("chargingStatus", "value")
    )
    charging_settings: ChargingSettings | None = Field(
        default=None, validation_alias=AliasPath("chargingSettings", "value")
    )
    plug_status: PlugStatus | None = Field(
        default=None, validation_alias=AliasPath("plugStatus", "value")
    )
    charge_mode: ChargeMode | None = Field(
        default=None, validation_alias=AliasPath("chargeMode", "value")
    )


class BatteryStatus(Base):
    current_soc_pct: int | None = Field(default=None, alias="currentSOC_pct")
    cruising_range_electric_km: int | None = Field(
        default=None, alias="cruisingRangeElectric_km"
    )


class ChargingStatus(Base):
    remaining: int | None = Field(
        default=None, alias="remaining_charging_time_to_complete_min"
    )
    charging_state: TCharging | None = None
    charge_mode: str | None = None
    charge_power_kw: float | None = Field(default=None, alias="chargePower_kW")
    charge_rate_kmph: int | None = Field(default=None, alias="chargeRate_kmph")
    charge_type: str | None = None
    charging_settings: str | None = None


class ChargingSettings(Base):
    max_charge_current_ac: str | None = None
    auto_unlock_plug_when_charged: bool | None = None
    auto_unlock_plug_when_charged_ac: bool | None = None
    target_soc_pct: int | None = None


class PlugStatus(Base):
    plug_connection_state: TConnected | None = None
    plug_lock_state: TLocked | None = None
    external_power: TActived | None = None
    led_color: str | None = None


class ChargeMode(Base):
    preferred_charge_mode: str | None = None
    available_charge_modes: list[str] | None = None


# SECTION
class Climatisation(Base):
    climatisation_settings: ClimatisationSettings | None = Field(
        default=None, validation_alias=AliasPath("climatisationSettings", "value")
    )
    climatisation_status: ClimatisationStatus | None = Field(
        default=None, validation_alias=AliasPath("climatisationStatus", "value")
    )
    window_heating_status: WindowHeatingStatus | None = Field(
        default=None, validation_alias=AliasPath("windowHeatingStatus", "value")
    )


class ClimatisationStatus(Base):
    remaining_climatisation_time_min: int | None = Field(
        default=None, alias="remainingClimatisationTime_min"
    )
    climatisation_state: Literal["off", "heating", "cooling"] | None = None


class ClimatisationSettings(Base):
    target_temperature_c: int | None = Field(default=None, alias="targetTemperature_C")
    target_temperature_f: int | None = Field(default=None, alias="targetTemperature_F")
    unit_in_car: str | None = None
    climatization_at_unlock: bool | None = None
    window_heating_enabled: bool | None = None
    zone_front_left_enabled: bool | None = None
    zone_front_right_enabled: bool | None = None
    zone_rear_left_enabled: bool | None = None
    zone_rear_right_enabled: bool | None = None


class WindowHeatingStatus(Base):
    state: TWindowHeating | None = None  # type: ignore


# SECTION
class ClimatisationTimers(Base):
    climatisation_timers_status: ClimatisationTimersStatus | None = Field(
        default=None, validation_alias=AliasPath("climatisationTimersStatus", "value")
    )


class ClimatisationTimersStatus(Base):
    time_in_car: datetime | None = None
    timers: list[Timer] | None = None


class Timer(Base):
    id: int
    enabled: bool
    single_timer: SingleTimer


class SingleTimer(Base):
    start: datetime | None = Field(alias="start_date_time", default=None)
    target: datetime | None = Field(alias="target_date_time", default=None)
    start_local: datetime | None = Field(alias="start_date_time_local", default=None)
    target_local: datetime | None = Field(alias="target_date_time_local", default=None)


# SECTION
class FuelStatus(Base):
    range_status: FuelRangeStatus | None = Field(
        default=None, validation_alias=AliasPath("rangeStatus", "value")
    )


class FuelRangeStatus(Base):
    car_type: str | None = None
    primary_engine: PrimaryEngine | None = None
    secondary_engine: SecondaryEngine | None = None
    total_range_km: int | None = Field(default=None, alias="totalRange_km")


class PrimaryEngine(Base):
    type: str | None = None
    current_soc_pct: int | None = Field(default=None, alias="currentSOC_pct")
    remaining_range_km: int | None = Field(default=None, alias="remainingRange_km")
    current_fuel_level_pct: int | None = Field(
        default=None, alias="currentFuelLevel_pct"
    )


class SecondaryEngine(Base):
    type: str | None = None
    current_soc_pct: int | None = Field(default=None, alias="currentSOC_pct")
    remaining_range_km: int | None = Field(default=None, alias="remainingRange_km")
    current_fuel_level_pct: int | None = Field(
        default=None, alias="currentFuelLevel_pct"
    )


# SECTION
class OilLevel(Base):
    oil_level_status: OilLevelStatus | None = Field(
        default=None, validation_alias=AliasPath("rangeStatus", "value")
    )


class OilLevelStatus(Base):
    value: bool


# SECTION
class VehicleLights(Base):
    lights_status: LightsStatus | None = Field(
        default=None, validation_alias=AliasPath("lightsStatus", "value")
    )


class LightsStatus(Base):
    lights: TLights | None = None  # type: ignore


# SECTION
class VehicleHealthInspection(Base):
    maintenance_status: MaintenanceStatus | None = Field(
        default=None, validation_alias=AliasPath("maintenanceStatus", "value")
    )


class MaintenanceStatus(Base):
    inspection_due_days: int | None = Field(default=None, alias="inspectionDue_days")
    inspection_due_km: int | None = Field(default=None, alias="inspectionDue_km")
    mileage_km: int | None = Field(default=None, alias="mileage_km")
    oil_service_due_days: int | None = Field(default=None, alias="oilServiceDue_days")
    oil_service_due_km: int | None = Field(default=None, alias="oilServiceDue_km")


# SECTION
class Measurements(Base):
    range_status: RangeStatus | None = Field(
        default=None, validation_alias=AliasPath("rangeStatus", "value")
    )
    odometer_status: OdometerStatus | None = Field(
        default=None, validation_alias=AliasPath("odometerStatus", "value")
    )
    fuel_level_status: FuelLevelStatus | None = Field(
        default=None, validation_alias=AliasPath("fuelLevelStatus", "value")
    )
    temperature_battery_status: TemperatureBatteryStatus | None = Field(
        default=None, validation_alias=AliasPath("temperatureBatteryStatus", "value")
    )


class RangeStatus(Base):
    electric_range: int | None = None
    gasoline_range: int | None = None
    total_range_km: int | None = Field(default=None, alias="totalRange_km")
    ad_blue_range: int | None = None


class OdometerStatus(Base):
    odometer: int | None = None


class FuelLevelStatus(Base):
    current_soc_pct: int | None = Field(default=None, alias="currentSOC_pct")
    current_fuel_level_pct: int | None = Field(
        default=None, alias="currentFuelLevel_pct"
    )
    primary_engine_type: str | None = None
    secondary_engine_type: str | None = None
    car_type: str | None = None


class TemperatureBatteryStatus(Base):
    temperature_hv_battery_max_k: float | None = Field(
        default=None, alias="temperatureHvBatteryMax_K"
    )
    temperature_hv_battery_min_k: float | None = Field(
        default=None, alias="temperatureHvBatteryMin_K"
    )


# SECTION
class VehicleHealthWarnings(Base):
    warning_lights: WarningLights | None = Field(
        default=None, validation_alias=AliasPath("temperatureBatteryStatus", "value")
    )


class WarningLights(Base):
    lights: TLights | None = None  # type: ignore


# SECTION
class Location(Base):
    addresses: list[Address] | None = Field(
        default=None, validation_alias=AliasPath("data")
    )


class Address(Base):
    id: str
    address: dict[str, Any]


# SECTION
class Position(Base):
    longitude: Longitude | None = Field(
        validation_alias=AliasPath("data", "lon"), default=None
    )
    latitude: Latitude | None = Field(
        validation_alias=AliasPath("data", "lat"), default=None
    )
    last_access: datetime | None = Field(
        validation_alias=AliasPath("data", "carCapturedTimestamp"), default=None
    )


# SECTION
class Information(Base):
    core: Core
    media: Media


class Core(Base):
    model_year: int


class Media(Base):
    short_name: str
    long_name: str


# SECTION
class DepartureProfiles(Base):
    departure_profiles_status: DepartureProfilesStatus | None = Field(
        default=None, validation_alias=AliasPath("departureProfilesStatus", "value")
    )


class DepartureProfilesStatus(Base):
    min_soc_pct: int | None = Field(default=None, alias="minSOC_pct")
    timers: list[dict[str, Any]] | None = None


##### GENERIC CLASS ####
class Model(Base):
    """Vehicle."""

    last_access: datetime = Field(
        validation_alias=AliasPath(
            "access", "accessStatus", "value", "carCapturedTimestamp"
        )
    )
    last_update: datetime = datetime.now()
    user_capabilities: UserCapabilities | None = None
    access: Access | None = None
    charging: Charging | None = None
    climatisation_timers: ClimatisationTimers | None = None
    climatisation: Climatisation | None = None
    fuel_status: FuelStatus | None = None
    oil_level: OilLevel | None = None
    vehicle_lights: VehicleLights | None = None
    vehicle_health_inspection: VehicleHealthInspection | None = None
    measurements: Measurements | None = None
    vehicle_health_warnings: VehicleHealthWarnings | None = None
    location: Location | None = None
    position: Position | None = None
    infos: Information | None = None
    departure_profiles: DepartureProfiles | None = None
