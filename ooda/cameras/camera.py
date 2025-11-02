from pydantic.dataclasses import dataclass

@dataclass
class RTSP:
    url: str


class Camera:

    def __init__(self):
        pass 

    def get_rtsp_url(self,*args, **kwargs)->RTSP:
        pass