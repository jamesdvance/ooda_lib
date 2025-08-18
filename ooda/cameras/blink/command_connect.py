import asyncio
from aiohttp import ClientSession
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth
from blinkpy.helpers.util import json_load

file_location = "/home/james/.auth/blink_auth.json" # TODO move to conf


async def start():
    blink = Blink()
    auth = Auth(await json_load(file_location))
    blink.auth = auth
    await blink.start()
    return blink

blink = asyncio.run(start())

for name, camera in blink.cameras.items():
    print(name)                   # Name of the camera
    print(camera.attributes)      # Print available attributes of camera