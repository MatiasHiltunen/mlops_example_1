# %%
from __future__ import annotations

import json
import os
from typing import List, Optional, Dict, Tuple, Any
import requests
from pydantic import BaseModel, Field, RootModel
from camera_history import ImageHistory, fetch_camera_history, ImageHistoryRoot
import polars as pl
from datetime import datetime, timedelta
import pathlib

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
    
    def get_station_coordinates(self) -> Dict[str, Tuple[float, float]]:
        """Returns a dictionary mapping station IDs to their coordinates"""
        coordinates = {}
        for feature in self.features:
            station_id = feature.properties.id
            coords = feature.geometry.coordinates
            coordinates[station_id] = (coords[0], coords[1])
        return coordinates
    
    def get_camera_coordinates(self) -> Dict[str, Tuple[float, float]]:
        """Returns a dictionary mapping camera IDs to station coordinates"""
        camera_coordinates = {}
        for feature in self.features:
            station_coords = feature.geometry.coordinates
            for preset_id in feature.get_preset_ids():
                camera_coordinates[preset_id] = (station_coords[0], station_coords[1])
        return camera_coordinates

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

    def download_images(self, output_dir: str = "./data/images"):
        """
        Downloads images for all cameras and saves them with coordinates and timestamps in filenames
        
        Args:
            output_dir: Directory where images will be saved
        """
        # Create output directory if it doesn't exist
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get coordinates for each camera
        camera_coords = self.get_camera_coordinates()
        
        # Fetch history data for each camera
        cameras = self.get_cameras()
        for camera_ids in cameras:
            for camera_id in camera_ids:
                history = fetch_camera_history(camera_id)
                if not history:
                    continue
                
                # Process each preset in the history
                for preset in history.presets:
                    # Process each image in the preset history
                    for image in preset.history:
                        # Get coordinates
                        coords = camera_coords.get(preset.id, (0, 0))
                        
                        # Parse timestamp from last_modified
                        try:
                            timestamp = datetime.fromisoformat(image.last_modified.replace('Z', '+00:00'))
                            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
                        except:
                            timestamp_str = "unknown_time"
                        
                        # Create filename with coordinates and timestamp
                        filename = f"{preset.id}_lat{coords[1]}_lon{coords[0]}_{timestamp_str}.jpg"
                        filepath = os.path.join(output_dir, filename)
                        
                        # Download the image if it doesn't exist
                        if not os.path.exists(filepath):
                            try:
                                image_response = requests.get(image.image_url)
                                if image_response.status_code == 200:
                                    with open(filepath, 'wb') as img_file:
                                        img_file.write(image_response.content)
                                    print(f"Downloaded: {filename}")
                                else:
                                    print(f"Failed to download {image.image_url}: HTTP {image_response.status_code}")
                            except Exception as e:
                                print(f"Error downloading {image.image_url}: {str(e)}")
                        else:
                            print(f"Image already exists, skipping: {filename}")

class Stations(RootModel):
    root: FeatureCollection

def get_stations() -> FeatureCollection:
    response = requests.get("https://tie.digitraffic.fi/api/weathercam/v1/stations?lastUpdated=false",headers={
            "Digitraffic-User": "Lapland University of Applied Sciences, Machine learning & AI"
        })

    if response.status_code != 200:
        raise Exception("Error listing stations")

    data = response.json()

    return Stations(data).root

def get_station_weather_data(station_id: str, timestamp: datetime = None) -> Optional[Dict[str, Any]]:
    """
    Fetch weather/sensor data for a specific station at a specific time or latest
    
    Args:
        station_id: The ID of the station (should be a weather station ID, not a camera ID)
        timestamp: Optional timestamp for historical data, if None gets latest data
        
    Returns:
        Dictionary containing sensor data or None if no data available
    """
    headers = {
        "Digitraffic-User": "Lapland University of Applied Sciences, Machine learning & AI"
    }
    
    try:
        if timestamp:
            # For historical data, use the history endpoint with time range
            # Calculate time range (30 minutes before and after the timestamp)
            from_time = (timestamp - timedelta(minutes=30)).isoformat() + "Z"
            to_time = (timestamp + timedelta(minutes=30)).isoformat() + "Z"
            
            url = f"https://tie.digitraffic.fi/api/weather/v1/stations/{station_id}/data/history?from={from_time}&to={to_time}"
            response = requests.get(url, headers=headers)
        else:
            # For latest data
            url = f"https://tie.digitraffic.fi/api/weather/v1/stations/{station_id}/data"
            response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch weather data for station {station_id}: HTTP {response.status_code}")
            return None
        
        data = response.json()
        return data
    except Exception as e:
        print(f"Error fetching weather data for station {station_id}: {str(e)}")
        return None

def get_camera_station_mapping() -> Dict[str, str]:
    """
    Creates a mapping from camera IDs to their corresponding weather station IDs
    
    Returns:
        Dictionary mapping camera IDs to station IDs
    """
    stations = get_stations()
    camera_to_station = {}
    
    # Print some debugging information to understand the structure
    print("DEBUG: Example feature properties:")
    if stations.features:
        example_feature = stations.features[0]
        print(f"Station ID: {example_feature.properties.id}")
        print(f"Station name: {example_feature.properties.name}")
        print(f"Presets/cameras: {example_feature.get_preset_ids()}")
        
        # Look for patterns in IDs - the first camera ID and station ID
        station_id = example_feature.properties.id
        camera_ids = example_feature.get_preset_ids()
        if camera_ids:
            camera_id = camera_ids[0]
            print(f"Comparing IDs - Station ID: {station_id}, Camera ID: {camera_id}")
    
    # First attempt: Map using the natural relationship in the FeatureCollection
    # Each Feature represents a station that has cameras (presets)
    for feature in stations.features:
        station_id = feature.properties.id
        for camera_id in feature.get_preset_ids():
            camera_to_station[camera_id] = station_id
    
    return camera_to_station

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

# Add a function to download images from the local data
def download_images_from_local_data(output_dir: str = "./data/images"):
    """
    Downloads images based on local station data with coordinates and timestamps in filenames.
    Also stores sensor/weather data in JSON files with the same base name.
    
    Args:
        output_dir: Directory where images will be saved
    """
    # Create output directory if it doesn't exist
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Print debug info about station IDs
    print_station_camera_debug_info(3)
    
    # Get stations data to extract coordinates
    stations = get_stations()
    camera_coords = stations.get_camera_coordinates()
    
    # Get camera to station mapping
    camera_to_station = get_camera_station_mapping()
    
    # Get local image history data
    history_data = get_local_image_data()
    
    # Counter for stats
    images_processed = 0
    images_skipped = 0
    
    # Process and download each image
    for history in history_data:
        for preset in history.presets:
            for image in preset.history:
                # Get coordinates
                coords = camera_coords.get(preset.id, (0, 0))
                
                # Parse timestamp from last_modified
                try:
                    timestamp = datetime.fromisoformat(image.last_modified.replace('Z', '+00:00'))
                    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
                except:
                    # Skip if we can't parse the timestamp
                    print(f"Skipping image with invalid timestamp: {image.image_url}")
                    continue
                
                # Get the station ID for this camera
                station_id = camera_to_station.get(preset.id)
                if not station_id:
                    print(f"Could not find station ID for camera {preset.id}, skipping")
                    continue
                
                # Create filenames with coordinates and timestamp
                base_filename = f"{preset.id}_lat{coords[1]}_lon{coords[0]}_{timestamp_str}"
                image_filepath = os.path.join(output_dir, f"{base_filename}.jpg")
                json_filepath = os.path.join(output_dir, f"{base_filename}.json")
                
                # Check if both image and weather data files already exist
                if os.path.exists(image_filepath) and os.path.exists(json_filepath):
                    print(f"Image and weather data already exist, skipping: {base_filename}")
                    images_skipped += 1
                    continue
                
                # If image exists but we're not fetching weather data
                if os.path.exists(image_filepath) and not os.path.exists(json_filepath):
                    # Skip weather data fetching if it failed before
                    skipped_weather_marker = os.path.join(output_dir, f"{base_filename}.noweather")
                    if os.path.exists(skipped_weather_marker):
                        print(f"Image exists and weather data previously failed, skipping: {base_filename}")
                        images_skipped += 1
                        continue
                
                # Fetch weather/sensor data for this station at this time
                weather_data = get_station_weather_data(station_id, timestamp)
                if not weather_data:
                    print(f"No weather data available for {preset.id} at {timestamp_str}, skipping")
                    # Create marker file to avoid repeated failures
                    if os.path.exists(image_filepath):
                        with open(os.path.join(output_dir, f"{base_filename}.noweather"), "w") as f:
                            f.write(f"Weather data fetch failed at {datetime.now().isoformat()}")
                    continue  # Skip if no weather data is available
                
                # Download the image and save weather data
                try:
                    # Save weather data
                    with open(json_filepath, 'w') as json_file:
                        json.dump(weather_data, json_file, indent=2)
                    
                    # Download the image if it doesn't exist
                    if not os.path.exists(image_filepath):
                        image_response = requests.get(image.image_url)
                        if image_response.status_code == 200:
                            with open(image_filepath, 'wb') as img_file:
                                img_file.write(image_response.content)
                            print(f"Downloaded: {base_filename}.jpg with weather data")
                            images_processed += 1
                        else:
                            print(f"Failed to download {image.image_url}: HTTP {image_response.status_code}")
                            # Remove the JSON file if image download failed
                            if os.path.exists(json_filepath):
                                os.remove(json_filepath)
                    else:
                        print(f"Image already exists but weather data was missing. Added weather data for: {base_filename}")
                        images_processed += 1
                except Exception as e:
                    print(f"Error processing {image.image_url}: {str(e)}")
                    # Clean up if there was an error
                    if os.path.exists(json_filepath):
                        os.remove(json_filepath)
    
    print(f"Processing complete. Downloaded/updated {images_processed} images, skipped {images_skipped} existing images.")

def modify_feature_collection_download_images():
    """
    Updates the FeatureCollection.download_images method to include weather data
    """
    # We'll modify the method directly instead of using this function
    pass

# Update the FeatureCollection.download_images method to include weather data
FeatureCollection.download_images = lambda self, output_dir="./data/images": download_images_with_weather_data(self, output_dir)

# Add a function to print debug info about station and camera IDs
def print_station_camera_debug_info(limit: int = 5):
    """
    Prints debug information about station and camera IDs to help understand the mapping
    
    Args:
        limit: Maximum number of stations to print
    """
    stations = get_stations()
    print("\n=== Station and Camera ID Debug Information ===")
    
    for i, feature in enumerate(stations.features):
        if i >= limit:
            break
            
        station_id = feature.properties.id
        station_name = feature.properties.name
        camera_ids = feature.get_preset_ids()
        
        print(f"\nStation {i+1}:")
        print(f"  ID: {station_id}")
        print(f"  Name: {station_name}")
        print(f"  Camera/Preset IDs: {camera_ids}")
        
        # Try to fetch weather data for this station
        try:
            weather_data = get_station_weather_data(station_id)
            weather_success = weather_data is not None
        except Exception:
            weather_success = False
            
        print(f"  Weather API works with this ID: {weather_success}")
    
    print("\n=== End Debug Information ===\n")

def download_images_with_weather_data(feature_collection: FeatureCollection, output_dir: str = "./data/images"):
    """
    Downloads images for all cameras and saves them with coordinates and timestamps in filenames.
    Also stores sensor/weather data in JSON files with the same base name.
    
    Args:
        feature_collection: The FeatureCollection containing station data
        output_dir: Directory where images will be saved
    """
    # Create output directory if it doesn't exist
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get coordinates for each camera
    camera_coords = feature_collection.get_camera_coordinates()
    
    # Print debug info about station IDs
    print_station_camera_debug_info(3)
    
    # Get camera to station mapping
    camera_to_station = {}
    for feature in feature_collection.features:
        station_id = feature.properties.id
        for camera_id in feature.get_preset_ids():
            camera_to_station[camera_id] = station_id
    
    # Fetch history data for each camera
    cameras = feature_collection.get_cameras()
    images_processed = 0
    images_skipped = 0
    
    for camera_ids in cameras:
        for camera_id in camera_ids:
            history = fetch_camera_history(camera_id)
            if not history:
                continue
            
            # Process each preset in the history
            for preset in history.presets:
                # Process each image in the preset history
                for image in preset.history:
                    # Get coordinates
                    coords = camera_coords.get(preset.id, (0, 0))
                    
                    # Parse timestamp from last_modified
                    try:
                        timestamp = datetime.fromisoformat(image.last_modified.replace('Z', '+00:00'))
                        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
                    except:
                        # Skip if we can't parse the timestamp
                        print(f"Skipping image with invalid timestamp: {image.image_url}")
                        continue
                    
                    # Get the station ID for this camera
                    station_id = camera_to_station.get(preset.id)
                    if not station_id:
                        print(f"Could not find station ID for camera {preset.id}, skipping")
                        continue
                    
                    # Create filenames with coordinates and timestamp
                    base_filename = f"{preset.id}_lat{coords[1]}_lon{coords[0]}_{timestamp_str}"
                    image_filepath = os.path.join(output_dir, f"{base_filename}.jpg")
                    json_filepath = os.path.join(output_dir, f"{base_filename}.json")
                    
                    # Check if both image and weather data files already exist
                    if os.path.exists(image_filepath) and os.path.exists(json_filepath):
                        print(f"Image and weather data already exist, skipping: {base_filename}")
                        images_skipped += 1
                        continue
                    
                    # If image exists but we're not fetching weather data
                    if os.path.exists(image_filepath) and not os.path.exists(json_filepath):
                        # Skip weather data fetching if it failed before
                        skipped_weather_marker = os.path.join(output_dir, f"{base_filename}.noweather")
                        if os.path.exists(skipped_weather_marker):
                            print(f"Image exists and weather data previously failed, skipping: {base_filename}")
                            images_skipped += 1
                            continue
                    
                    # Fetch weather/sensor data for this station at this time
                    weather_data = get_station_weather_data(station_id, timestamp)
                    if not weather_data:
                        print(f"No weather data available for {preset.id} at {timestamp_str}, skipping")
                        # Create marker file to avoid repeated failures
                        if os.path.exists(image_filepath):
                            with open(os.path.join(output_dir, f"{base_filename}.noweather"), "w") as f:
                                f.write(f"Weather data fetch failed at {datetime.now().isoformat()}")
                        continue  # Skip if no weather data is available
                    
                    # Download the image and save weather data
                    try:
                        # Save weather data
                        with open(json_filepath, 'w') as json_file:
                            json.dump(weather_data, json_file, indent=2)
                        
                        # Download the image if it doesn't exist
                        if not os.path.exists(image_filepath):
                            image_response = requests.get(image.image_url)
                            if image_response.status_code == 200:
                                with open(image_filepath, 'wb') as img_file:
                                    img_file.write(image_response.content)
                                print(f"Downloaded: {base_filename}.jpg with weather data")
                                images_processed += 1
                            else:
                                print(f"Failed to download {image.image_url}: HTTP {image_response.status_code}")
                                # Remove the JSON file if image download failed
                                if os.path.exists(json_filepath):
                                    os.remove(json_filepath)
                        else:
                            print(f"Image already exists but weather data was missing. Added weather data for: {base_filename}")
                            images_processed += 1
                    except Exception as e:
                        print(f"Error processing {image.image_url}: {str(e)}")
                        # Clean up if there was an error
                        if os.path.exists(json_filepath):
                            os.remove(json_filepath)
    
    print(f"Processing complete. Downloaded/updated {images_processed} images, skipped {images_skipped} existing images.")

# Update the main download_images_from_local_data function
download_images_from_local_data_original = download_images_from_local_data
# No need to reassign to itself

# %%

stations = get_stations()

# %%

stations.download_images()

""" images = get_local_image_data() """

# %%

# Example usage: Download images with weather data
# stations = get_stations()
# stations.download_images()  # Direct from API

# Or from local data
# download_images_from_local_data()

# Example to run:
# stations = get_stations()
# stations.download_images("./data/weather_images")  # With weather data

# %%

# Debug ID mapping
# print_station_camera_debug_info(10)  # Uncomment to see ID relationships

# %%

# images = get_local_image_data()
# print(images)
# for image_data in images:
#    print(image_data.get_image_urls())

# %%
