from __future__ import annotations
import requests
from typing import List
from pydantic import BaseModel, RootModel
from dotenv import load_dotenv
import os

# https://www.digitraffic.fi/tieliikenne/#restjson-rajapinnat

LIST_STATIONS = "https://tie.digitraffic.fi/api/weathercam/v1/stations"

DATA = LIST_STATIONS + "/data"

class CameraVariant(BaseModel):
    name: str
    id: str

class CameraLocation(BaseModel):
    name: str
    lat: float
    lon: float
    variants: List[CameraVariant]

class CameraList(RootModel):
    root: List[CameraLocation]

response = requests.get("https://infraweb-rws.fi/infralink/cams/camlist", headers={
    "apiToken": API_KEY,
    "content-type": "application/json"
})

data = response.json()

cameras = CameraList(data)

# print(cameras)

for camera in cameras.root:
    print("-------------------------------------------")
    print(camera.name)
    print(camera.lat, camera.lon)
    [print(obj) for obj in camera.variants]
