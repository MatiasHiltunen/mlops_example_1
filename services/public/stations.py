# %%
from __future__ import annotations

import json
import os
from typing import List, Optional
import requests
from pydantic import BaseModel, Field, RootModel
from camera_history import ImageHistory, fetch_camera_history, ImageHistoryRoot
import polars as pl

class Geometry(BaseModel):
    type: str
    coordinates: List[float]


class Preset(BaseModel):
    id: str
    in_collection: bool = Field(..., alias='inCollection')


class Properties(BaseModel):
    id: str
    name: str
    collection_status: str = Field(..., alias='collectionStatus')
    state: Optional[str]
    data_updated_time: str = Field(..., alias='dataUpdatedTime')
    presets: List[Preset]

    def get_preset_id(self):
        return [preset.id for preset in self.presets]

class Feature(BaseModel):
    type: str
    id: str
    geometry: Geometry
    properties: Properties

    def get_preset_ids(self):
        return self.properties.get_preset_id()

class FeatureCollection(BaseModel):
    type: str
    data_updated_time: str = Field(..., alias='dataUpdatedTime')
    features: List[Feature]

    def get_cameras(self):
        properties = [feature.get_preset_ids() for feature in self.features]
        return properties
    
    def get_stations(self):
        return [feature.properties.id for feature in self.features]
    


    def get_image_data(self):
        cameras = self.get_cameras()
        
        history_images: List[ImageHistory | None] = []

        dir_list = os.listdir("./data/stations") 

        for camera_ids in cameras:
            for camera_id in camera_ids:
                if camera_id + ".json" in dir_list:
                    continue
                
                history = fetch_camera_history(camera_id)
                
                if not history:
                    continue

                try:
                    with open( "./data/stations/" + camera_id + ".json", "x") as f:
                        f.write(history.model_dump_json())
                except FileExistsError:
                    print("Already exists.")

                history_images.append(history) 




        return history_images

            


class Stations(RootModel):
    root: FeatureCollection

def get_stations() -> FeatureCollection:


    response = requests.get("https://tie.digitraffic.fi/api/weathercam/v1/stations?lastUpdated=false",headers={
            "Digitraffic-User": "Lapland University of Applied Sciences, Machine learning & AI"
        })

    if response.status_code is not 200:
        raise Exception("Error listing stations")

    data = response.json()

    return Stations(data).root


def get_local_image_data() -> List[ImageHistory]:

    dir_list = os.listdir("./data/stations")

    history_data = []
        
    for item in dir_list:
        try:
            with open( "./data/stations/" + item, "r") as f:
                file = f.read()

                data = json.loads(file)
                
  

                

                history_data.append(ImageHistoryRoot(data).root)

        except FileExistsError:
            print("Error reading file")

    return history_data

# %%

""" stations = get_stations() """


# %%

""" images = stations.get_image_data() """

images = get_local_image_data()

# %%

print(images)


for image_data in images:
    print(image_data.get_image_urls())


# %%
