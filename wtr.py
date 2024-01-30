import requests
import schedule
import logging
import time
import configparser
from gpiozero import LED
from phue import Bridge

ECOWITT_HOST = "https://api.ecowitt.net/api/v3/"
DEVICE_INFO_URL = "device/info?application_key={appkey}&api_key={apikey}&mac={mac}"

CONFIG_FILE = "config.ini"

rest_period_counter = 0
rest_active = False

config = None

url = ""

hue = None

relay = None

def main():
    global config
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    global url
    url = ECOWITT_HOST + DEVICE_INFO_URL.format(appkey = config["EcoWitt"]["AppKey"], 
                                                apikey = config["EcoWitt"]["ApiKey"],
                                                mac = config["EcoWitt"]["DeviceMac"])
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("wtr.log"),
            logging.StreamHandler()
        ]
    )
    
    global hue
    hue = Bridge(config["Hue"]["BridgeIp"])
    #Uncomment this line on first run
    #hue.connect()
    
    global relay
    relay = LED(int(config["Relay"]["GpioPin"]))
    
    schedule.every().minute.do(check_for_watering)
    schedule.every(5).seconds.do(check_for_leak)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def check_for_watering():
    global rest_active
    global rest_period_counter
    
    humidity = get_humidity_status(config["EcoWitt"]["SoilSensorId"])
    
    if humidity <= int(config["Logic"]["HumidityThresholdPercent"]):
        logging.info("Humidity above threshold (" + config["Logic"]["HumidityThresholdPercent"] + ")")
        if rest_active:
            logging.info("Rest period active, skipping watering")
            rest_period_counter += 1
            if rest_period_counter >= int(config["Logic"]["RestPeriodMinutes"]):
                logging.info("Rest period over")
                rest_active = False
                rest_period_counter = 0
        else:
            start_watering()
            rest_active = True
        
    
def start_watering():
    logging.info("Starting watering")
    relay.on()
    time.sleep(int(config["Logic"]["WateringDurationSeconds"]))
    relay.off()
    logging.info("Watering done")

def get_humidity_status(sensor: str):
    device_info = requests.get(url).json()
    
    if device_info["msg"] == "success":
        soil = device_info["data"]["last_update"][sensor]["soilmoisture"]["value"]
        logging.info("Soil humidity: " + soil + "%")
        return int(soil)
    else:
        logging.error("Error fetching ecowitt data: " + device_info["msg"])
        exit()   

def check_for_leak():
     device_info = requests.get(url).json()
     
     if device_info["data"]["last_update"]["water_leak"][config["EcoWitt"]["LeakSensorId"]]["value"] == "1":
        logging.warning("Leak detected!")
        hue.set_light(int(config["Hue"["SwitchId"]]), 'on', False)
        relay.off()
        exit()
        

if __name__ == '__main__':
    main()