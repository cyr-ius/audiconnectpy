# audiconnectpy

Fetch data vehicle from Audi API

Check your config, fetch fata sensors.Perform actions within the limits of your rights

## Warning

Use this API with care. If you use it wrong (e.g. too many logins, repeated login attempts with wrong password, ...) your account may get blocked.

## Install

Use the PIP package manager

```bash
pip install audiconnectpy
```

Or manually download and install the last version from github

```bash
git clone https://github.com/cyr-ius/audiconnectpy.git
python setup.py install
```

## Get started

```python
# Import the audiconnectpy package.
from audiconnectpy import AudiConnect

async def main():
    async with ClientSession() as session:
        api = AudiConnect(session, VW_USERNAME, VW_PASSWORD, COUNTRY, SPIN)
        await api.async_update()
        print(api.vehicles)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

Have a look at the [example.py](https://github.com/cyr-ius/audiconnectpy/blob/master/example.py) for a more complete overview.

## Login & Consent

Audiconectpy is based on the new Carnet ID API that was introduced with the new series of ID cars. If you use another car or hybrid you probably need to agree to the terms and conditions of the My Audi interface. Easiest to do so is by installing the My Audi app on your smartphone and login there. If necessary you will be asked to agree to the terms and conditions.

## Credits

Inspired by arjenvrh/audi_connect_ha from github and tknaller/openhab-addons
