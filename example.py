"""Example script."""
import asyncio
import logging

from aiohttp import ClientSession

from audiconnectpy import AudiConnect, AudiException

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# create console handler and set level to debug
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

_LOGGER = logging.getLogger(__name__)

VW_USERNAME = "xxxxxx@xxxx.xxx"
VW_PASSWORD = "xxxxxxx"
COUNTRY = "DE"
SPIN = 1234


async def main() -> None:
    """Init method."""
    async with ClientSession() as session:
        api = AudiConnect(session, VW_USERNAME, VW_PASSWORD, COUNTRY, SPIN)

        try:
            await api.async_update()

            for vin, vehicle in api.vehicles.items():
                _LOGGER.info(vin)
                _LOGGER.info(vehicle.model)
                _LOGGER.info(vehicle.support_charger)
                _LOGGER.info(vehicle.support_climater)
                _LOGGER.info(vehicle.support_cyclic)
                _LOGGER.info(vehicle.support_long_term)
                _LOGGER.info(vehicle.support_position)
                _LOGGER.info(vehicle.support_preheater)
                _LOGGER.info(vehicle.support_short_term)
                _LOGGER.info(vehicle.support_vehicle)

                for attr, state in vehicle.states.items():
                    _LOGGER.info("%s: %s", attr, state.get("value"))
        except AudiException as error:
            _LOGGER.error(error)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
