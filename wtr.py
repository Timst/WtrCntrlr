import requests
import schedule
import logging
import time
import configparser
from gpiozero import LED
from phue import Bridge

from plant import Plant

CONFIG_FILE = "config.ini"
config = None

ECOWITT_HOST = "https://api.ecowitt.net/api/v3/"
DEVICE_INFO_URL = "device/info?application_key={appkey}&api_key={apikey}&mac={mac}"
url = ""

hue = None

lemon = None
orange = None

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
    
    global lemon
    lemon = Plant(name= "Lemon", 
                  relay= LED(int(config["Relay"]["GpioPin1"])), 
                  sensor_id=config["EcoWitt"]["SoilSensorId1"], 
                  watering_threshold=int(config["Logic"]["HumidityThresholdPercent1"]))
    
    global orange
    orange = Plant(name= "Orange", 
                  relay= LED(int(config["Relay"]["GpioPin2"])), 
                  sensor_id=config["EcoWitt"]["SoilSensorId2"], 
                  watering_threshold=int(config["Logic"]["HumidityThresholdPercent2"]))
    
    schedule.every().minute.do(check_for_watering)
    schedule.every(5).seconds.do(check_for_leak)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def check_for_watering():
    check_plant(lemon)
    check_plant(orange)
           
def check_plant(plant: Plant):
    humidity = get_humidity_status(plant)
    
    if humidity <= plant.watering_threshold:
        logging.info("Humidity of " + plant.name + " at " + humidity  + "%, below threshold (" + plant.watering_threshold + "%)")
        if plant.rest_active:
            logging.info("Rest period active, skipping watering")
            plant.rest_period_counter += 1
            if plant.rest_period_counter >= int(config["Logic"]["RestPeriodMinutes"]):
                logging.info("Rest period over")
                plant.rest_active = False
                plant.rest_period_counter = 0
        else:
            start_watering(plant)
            plant.rest_active = True
    
def start_watering(plant: Plant):
    logging.info("Starting watering" + plant.name)
    
    plant.relay.on()
    time.sleep(int(config["Logic"]["WateringDurationSeconds"]))
    plant.relay.off()
    
    logging.info("Watering done")

def get_humidity_status(plant: Plant):
    device_info = requests.get(url).json()
    
    if device_info["msg"] == "success":
        soil = device_info["data"]["last_update"][plant.sensor_id]["soilmoisture"]["value"]
        logging.info("Soil humidity of " + plant.name + ": " + soil + "%")
        return int(soil)
    else:
        logging.error("Error fetching ecowitt data: " + device_info["msg"])
        exit()   

def check_for_leak():
     device_info = requests.get(url).json()
     
     if device_info["data"]["last_update"]["water_leak"][config["EcoWitt"]["LeakSensorId"]]["value"] == "1":
        logging.warning("Leak detected!")
        hue.set_light(int(config["Hue"]["SwitchId"]), 'on', False)
        lemon.relay.off()
        orange.relay.off()
        exit()
        
if __name__ == '__main__':
    main()