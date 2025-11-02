import asyncio
from camera import Camera
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

def get_cameras(blink:Blink):
    names, cameras = [], []
    for name, camera in blink.cameras.items():
        names.append(name)
        cameras.append(camera)


class BlinkCamera(Camera):

    def _start_camera(self):
        return blink.get_live_stream()

    def get_rtsp_url(self, *args, **kwargs):
        super().get_rtsp_url(*args, **kwargs)
        return blink.