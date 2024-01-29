import requests
import json

ECOWITT_HOST = "https://api.ecowitt.net/api/v3/"
DEVICE_INFO_URL = "device/info?application_key={appkey}&api_key={apikey}&mac={mac}"

CRED_FILE = "cred"

def main():
    cred = open(CRED_FILE).read().splitlines()
    
    url = ECOWITT_HOST + DEVICE_INFO_URL.format(appkey = cred[0], apikey = cred[1], mac = cred[2])
    
    device_info = requests.get(url).json()
    
    if device_info["msg"] == "success":
        soil = device_info["data"]["last_update"]["soil_ch1"]["soilmoisture"]["value"]
        print("Soil humidity: " + soil + "%")
    else:
        print("Error fetching ecowitt data: " + device_info["msg"])
    

if __name__ == '__main__':
    main()