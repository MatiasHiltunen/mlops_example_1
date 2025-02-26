import json
import requests
import os
from things_board_rest_api_client import Client


from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("API_ACCOUNT")
PASSWORD = os.getenv("API_PASSWORD")

BASE_URL = "https://www.infraweb-rws.fi/api"


access_token = None

def authorize():
    
    response = requests.post(BASE_URL + "/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    }, headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    if not response.ok:
        print("response failed with status code" + str(response.status_code))
        raise Exception("Login was not successful")
    
    data = response.json()
    
    return data

def get_company_api(endpoint):
    global access_token
    
    if not access_token:
        auth_data = authorize()
        access_token = auth_data["token"]
    
    response = requests.get(BASE_URL + endpoint, headers={
        "Content-Type": "application/json",
        "X-Authorization": "Bearer " + access_token
    })
    
    if not response.ok:
        print("response failed with status code"+ str(response.status_code))
        raise Exception("Login was not successful")
    
    data = response.json()
    
    return data

def get_entityview():
    
    view_types = get_company_api("/entityView/types")

    """Example response: [{
        'tenantId': {
            'entityType': 'TENANT', 'id': '82737eb0-e429-11e9-ac8f-fdcdec2c26a2'}, 'entityType': 'ENTITY_VIEW', 'type': 'Friction'}, 
            {'tenantId': {'entityType': 'TENANT', 'id': '82737eb0-e429-11e9-ac8f-fdcdec2c26a2'}, 'entityType': 'ENTITY_VIEW', 'type': 'JKL - WeatherStations'}, 
            {'tenantId': {'entityType': 'TENANT', 'id': '82737eb0-e429-11e9-ac8f-fdcdec2c26a2'}, 
            'entityType': 'ENTITY_VIEW', 'type': 'Test'}] """
    
    return view_types

def get_entity_info():
    
    data = get_company_api("/deviceInfos/all?pageSize=10&page=1&includeCustomers=true&active=true")
    
    print(data)
    #get_company_api("/api/plugins/telemetry/{entityType}/{entityId}/keys/attributes")



def get_access_info():
    
    access_data = get_company_api("/permissions/allowedPermissions")

    print(json.dumps(access_data))

