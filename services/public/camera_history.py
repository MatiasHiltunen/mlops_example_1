


from __future__ import annotations

import os
from typing import List

from pydantic import AliasChoices, BaseModel, RootModel, Field
import requests
import json

class HistoryItem(BaseModel):
    last_modified: str = Field(..., alias = AliasChoices('last_modified', 'lastModified'))
    image_url: str = Field(..., alias=AliasChoices('image_url', 'imageUrl'))
    size_bytes: int = Field(..., alias=AliasChoices('size_bytes', 'sizeBytes'))


class Preset(BaseModel):
    data_updated_time: str = Field(..., alias=AliasChoices('data_updated_time', 'dataUpdatedTime'))
    history: List[HistoryItem]
    id: str


class ImageHistory(BaseModel):
    id: str
    data_updated_time: str = Field(..., alias=AliasChoices('data_updated_time', 'dataUpdatedTime'))
    presets: List[Preset]

    def get_image_urls(self):

        urls = []

        [[urls.append(history.image_url) for history in preset.history] for preset in self.presets]

        return urls

class ImageHistoryRoot(RootModel):
    root: ImageHistory

def fetch_camera_history(id: str) -> ImageHistory | None:

    try:

        response = requests.get("https://tie.digitraffic.fi/api/weathercam/v1/stations/" + id +  "/history", headers={
            "Digitraffic-User": "Lapland University of Applied Sciences, Machine learning & AI"
        })


        if response.status_code != 200:
            raise Exception("Error fetching station")
        

        data = response.json()


        return ImageHistoryRoot(data).root
    
    except:

        print("Error loading camera history with id: ", id)

        return None
