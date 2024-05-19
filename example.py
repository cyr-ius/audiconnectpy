"""Example."""

import asyncio
import logging

from aiohttp import ClientSession
import yaml

from audiconnectpy import AudiConnect, AudiException

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")
# logger.setLevel("INFO")
# create console handler and set level to debug
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


# Fill out the secrets in secrets.yaml, you can find an example
# _secrets.yaml file, which has to be renamed after filling out the secrets.

with open("./secrets.yaml", encoding="UTF-8") as file:
    secrets = yaml.safe_load(file)

USERNAME = secrets["USERNAME"]
PASSWORD = secrets["PASSWORD"]
COUNTRY = "FR"
SPIN = secrets["SPIN"]


async def main() -> None:
    """Run Main method."""
    async with ClientSession() as session:
        api = AudiConnect(session, USERNAME, PASSWORD, COUNTRY, SPIN)

        try:
            await api.async_login()
            if api.is_connected:
                for vehicle in api.vehicles:
                    logger.info(vehicle.vin)
                    logger.info(vehicle.infos)
                    logger.info(vehicle.fuel_status)
                    logger.info(vehicle.last_access)
                    logger.info(vehicle.position)
                    # logger.info(vehicle.location)
                    logger.info(vehicle.access)
                    logger.info(vehicle.charging)
                    logger.info(vehicle.climatisation)
                    logger.info(vehicle.climatisation_timers)
                    logger.info(vehicle.oil_level)
                    logger.info(vehicle.vehicle_lights)
                    logger.info(vehicle.vehicle_health_inspection)
                    logger.info(vehicle.measurements)
                    logger.info(vehicle.vehicle_health_warnings)
                    logger.info(vehicle.infos)
                    # await vehicle.async_set_lock(True)
                    # await vehicle.async_refresh_vehicle_data()
                    # await vehicle.async_update()
                    logger.info(vehicle.last_access)
        except AudiException as error:
            logger.error(error)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(main())
