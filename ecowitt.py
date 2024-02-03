import requests
import logging

from plant import Plant

class LocalEcowitt:
    url = ""
    
    def __init__(self, ip: str):
        self.url = "http://" + ip + "/get_livedata_info"
        
    def get_humidity(self, plant: Plant) -> int:
        device_info = get_device_info(self.url)
        sensor = next(filter(lambda x:x["channel"]==plant.sensor_channel, device_info["ch_soil"]))
        return int(sensor["humidity"].replace("%", ""))
    
    def is_leaking(self, channel: str) -> bool:
        device_info = get_device_info(self.url)
        sensor = next(filter(lambda x:x["channel"]==channel, device_info["ch_leak"]))
        return sensor["status"] != "Normal"
    
class NetEcowitt:
    url = ""
    
    def __init__(self, appKey: str, apiKey: str, deviceMac: str):
        self.url =  "https://api.ecowitt.net/api/v3/device/info?application_key={appkey}&api_key={apikey}&mac={mac}".format(
            appkey = appKey, 
            apikey = apiKey,
            mac = deviceMac)
        
    def get_humidity(self, plant: Plant) -> int:
        device_info = get_device_info(self.url)
        
        if device_info is None:
            return 100
        else:
            if device_info["msg"] == "success":
                return int(device_info["data"]["last_update"]["soil_ch" + plant.sensor_channel]["soilmoisture"]["value"])
            else:
                logging.error("Error fetching humidity data of " + plant.name + ": " + device_info["msg"])
                return 100
    
    def is_leaking(self, channel: str) -> bool:
        device_info = get_device_info(self.url)
        
        if device_info["msg"] == "success":
            return device_info["data"]["last_update"]["water_leak"]["leak_ch" + channel]["value"] == "1"
        else:
            logging.error("Error fetching leak sensor data on channel #" + channel + ": " + device_info["msg"])
            return False
        
def get_device_info(url):
    try:
        return requests.get(url).json()
    except requests.exceptions.RequestException as e:
        logging.error("Error fetching ecowitt data: " + e)