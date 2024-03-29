import json
import logging
import requests

from plant import Plant

class LocalEcowitt:
    url = ""

    def __init__(self, ip: str):
        self.url = f"http://{ip}/get_livedata_info"

    def get_humidity(self, plant: Plant) -> int:
        device_info = get_device_info(self.url)

        if device_info is None:
            return 100

        sensor = next(filter(lambda x:x["channel"]==plant.sensor_channel, device_info["ch_soil"]))
        return int(sensor["humidity"].replace("%", ""))

    def is_leaking(self, channel: str) -> bool:
        device_info = get_device_info(self.url)

        if device_info is None:
            return False

        sensor = next(filter(lambda x:x["channel"]==channel, device_info["ch_leak"]))
        return sensor["status"] != "Normal"

class NetEcowitt:
    url = ""

    def __init__(self, app_key: str, api_key: str, device_mac: str):
        self.url =  f"https://api.ecowitt.net/api/v3/device/info?application_key={app_key}&api_key={api_key}&mac={device_mac}"

    def get_humidity(self, plant: Plant) -> int:
        device_info = get_device_info(self.url)

        if device_info is None:
            return 100

        if device_info["msg"] == "success":
            return int(device_info["data"]["last_update"]["soil_ch" + plant.sensor_channel]["soilmoisture"]["value"])
        else:
            logging.error(f"Error fetching humidity data of {plant.name}: {json.dumps(device_info['msg'])}")
            return 100

    def is_leaking(self, channel: str) -> bool:
        device_info = get_device_info(self.url)

        if device_info is None:
            return False

        if device_info["msg"] == "success":
            return device_info["data"]["last_update"]["water_leak"]["leak_ch" + channel]["value"] == "1"
        else:
            logging.error(f"Error fetching leak sensor data on channel #{channel}: {json.dumps(device_info['msg'])}")
            return False

def get_device_info(url):
    logging.debug(f"Fetching {url}")
    try:
        return requests.get(url, timeout=30).json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None
