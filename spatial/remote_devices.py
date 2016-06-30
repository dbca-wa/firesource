import json
from datetime import datetime, timedelta
from settings import SSS_URL

from dpaw_utils import requests

SSS_DEVICES_URL = SSS_URL + '/api/v1/device/?limit=10000&seen_age__lte=10080&point__isnull=false&format=json'
SSS_DEVICE_URL = SSS_URL + "/api/v1/device/?deviceid={0}&format=json"
SSS_HISTORY_URL = SSS_URL + "/api/v1/loggedpoint/?limit=10000&device={0}&seen__gte={1}&seen__lte={2}&format=json"

def makefeatures(devices):
    featureCollection = {
        "crs": None,
        "type": "FeatureCollection",
        "features": []
    }

    for device in devices:
        point = device["point"].split("(")[1].replace(")", "").split(" ")
        seen = datetime.strptime(device["seen"], "%Y-%m-%dT%H:%M:%S")
        delta = datetime.now() - seen
        age_minutes = delta.days * 24 * 60 + delta.seconds // 60
        data = {
            "geometry": {
                "type": "Point",
                "coordinates": [float(point[0]), float(point[1])],
            },
            "type": "Feature",
            "id": device["id"],
            "properties": {
                "name": device["name"],
                "tags": "",
                "altitude": device["altitude"],
                "heading": device["heading"],
                "symbol": device["icon"].replace("sss-", "device/"),
                "callsign": device["callsign"],
                "deviceid": device["deviceid"],
                "velocity": device["velocity"],
                "logged_time": (seen - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S"),
                "age": (age_minutes / 60) + 1
            }
        }
        featureCollection["features"].append(data)

    return featureCollection

def remote_devices(request):
    #NEW_SSS_DEVICES = 'https://sss.dpaw.wa.gov.au/api/v1/device/?limit=10000&point__isnull=false&format=json'
    #devices = json.loads(requests.get(request, NEW_SSS_DEVICES).content)["objects"]
    devices = json.loads(requests.get(request, SSS_DEVICES_URL).content)["objects"]
    featureCollection = makefeatures(devices)
    return json.dumps(featureCollection)

def remote_history(request,postdict):
    """
    Sample postdict:
        {"from_date":"2015-01-06 00:40","to_date":"2015-01-06 03:40","unique_list":["300034012174320"]}
    """
    devices = list()
    
    for device in postdict["unique_list"]:
        device = json.loads(requests.get(request,SSS_DEVICE_URL.format(device)).content)["objects"][0]
        params = [
            device["id"],
            postdict["from_date"] + "Z",
            postdict["to_date"] + "Z"
        ]
        points =  json.loads(requests.get(request,SSS_HISTORY_URL.format(*params)).content)["objects"]
        for point in points:
            row = device.copy()
            row.update(point)
            devices.append(row)
    featureCollection = makefeatures(devices)
    return json.dumps(featureCollection)
