import requests
import schedule
import logging
import time
import configparser
from gpiozero import LED
from phue import Bridge
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path

from plant import Plant

CONFIG_FILE = "config.ini"
config = None

ECOWITT_HOST = "https://api.ecowitt.net/api/v3/"
DEVICE_INFO_URL = "device/info?application_key={appkey}&api_key={apikey}&mac={mac}"
url = ""

hue = None
camera = None
camera_start_time = None
camera_end_time = None

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
    
    global camera
    Path(config["Camera"]["Folder"]).mkdir(exist_ok=True)

    camera = Picamera2()
    camera_config = camera.create_still_configuration()
    camera.configure(camera_config)
    
    if bool(config["Camera"]["Crop"]):      
        camera.set_controls({"ScalerCrop":(
            int(config["Camera"]["X"]), 
            int(config["Camera"]["Y"]), 
            int(config["Camera"]["Width"]),
            int(config["Camera"]["Height"]),
        )})
        
    if bool(config["Camera"]["TimeLimit"]):
        global camera_start_time, camera_end_time
        camera_start_time = datetime.strptime(config["Camera"]["StartTime"], "%H:%M:%S")
        camera_end_time = datetime.strptime(config["Camera"]["EndTime"], "%H:%M:%S")
            
    camera.start()

    global lemon
    lemon = Plant(name= "Lemon", 
                  relay= LED(int(config["Relay"]["GpioPinLemon"])), 
                  sensor_id=config["EcoWitt"]["SoilSensorIdLemon"], 
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentLemon"]))
    
    global orange
    orange = Plant(name= "Orange", 
                  relay= LED(int(config["Relay"]["GpioPinOrange"])), 
                  sensor_id=config["EcoWitt"]["SoilSensorIdOrange"], 
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentOrange"]))
    
    schedule.every(int(config["Watering"]["WaterCheckFrequencySeconds"])).seconds.do(check_for_watering)
    schedule.every(int(config["Watering"]["LeakCheckFrequencySeconds"])).seconds.do(check_for_leak)
    schedule.every(int(config["Camera"]["FrequencySeconds"])).seconds.do(snap_pic)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def check_for_watering():
    check_plant(lemon)
    check_plant(orange)
           
def check_plant(plant: Plant):
    humidity = get_humidity_status(plant)
    
    if humidity <= plant.watering_threshold:
        logging.info("Humidity of " + plant.name + " at " + str(humidity)  + "%, at or below threshold (" + str(plant.watering_threshold) + "%)")
        if plant.rest_active:
            logging.info("Rest period active, skipping watering")
            plant.rest_period += 1
            if plant.rest_period >= int(config["Watering"]["RestPeriodMinutes"]):
                logging.info("Rest period over")
                plant.rest_active = False
                plant.rest_period = 0
        else:
            start_watering(plant)
            plant.rest_active = True
    
def start_watering(plant: Plant):
    logging.info("Starting watering " + plant.name)
    
    plant.relay.on()
    time.sleep(int(config["Watering"]["WateringDurationSeconds"]))
    plant.relay.off()
    
    logging.info("Watering done")

def get_humidity_status(plant: Plant):
    try:
        device_info = requests.get(url).json()
    
        if device_info["msg"] == "success":
            soil = device_info["data"]["last_update"][plant.sensor_id]["soilmoisture"]["value"]
            logging.info("Soil humidity of " + plant.name + ": " + soil + "%")
            return int(soil)
        else:
            logging.error("Error fetching ecowitt data: " + device_info["msg"])
            exit() 
    except:
        logging.warning("Couldn't retrieve " + plant.sensor_id + "  status")  
        return 100 

def check_for_leak():
    try:
        device_info = requests.get(url).json()
        
        if device_info["data"]["last_update"]["water_leak"][config["EcoWitt"]["LeakSensorId"]]["value"] == "1":
            logging.warning("Leak detected!")
            hue.set_light(int(config["Hue"]["SwitchId"]), 'on', False)
            lemon.relay.off()
            orange.relay.off()
            exit()
    except:
        logging.warning("Couldn't retrieve leak sensor status")

def snap_pic():
    
    if bool(config["Camera"]["TimeLimit"]):
        start_time = datetime.now().replace(hour=camera_start_time.hour, minute=camera_start_time.minute, second=camera_start_time.second)
        end_time = datetime.now().replace(hour=camera_end_time.hour, minute=camera_end_time.minute, second=camera_end_time.second)
        now = datetime.now()
        
        if now < start_time or now > end_time:
            logging.info("Outside of camera operating hours, skipping capture")
            return
           
    file_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png")
    path = config["Camera"]["Folder"] + "/" + file_name
    camera.capture_file(path)
    logging.info("Picture captured and saved to " + path)
        
if __name__ == '__main__':
    main()