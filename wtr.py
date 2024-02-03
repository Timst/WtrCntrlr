import sys
import schedule
import logging
import time
import configparser
from gpiozero import LED, CPUTemperature
from phue import Bridge
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path

from plant import Plant
from ecowitt import LocalEcowitt, NetEcowitt

CONFIG_FILE = "config.ini"
config = None

ecowitt = None

hue = None
camera = None
camera_start_time = None
camera_end_time = None

lemon = None
orange = None

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("wtr.log"),
            logging.StreamHandler()
        ]
    )

    global config
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    global ecowitt
    if config["EcoWitt"]["Mode"] == "Local":
        ecowitt = LocalEcowitt(config["EcoWitt"]["IP"])
    elif config["EcoWitt"]["Mode"] == "Net":
        ecowitt = NetEcowitt(config["EcoWitt"]["AppKey"], config["EcoWitt"]["ApiKey"], config["EcoWitt"]["DeviceMac"])

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
                  sensor_channel=config["EcoWitt"]["SoilSensorChannelLemon"],
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentLemon"]))

    global orange
    orange = Plant(name= "Orange",
                  relay= LED(int(config["Relay"]["GpioPinOrange"])),
                  sensor_channel=config["EcoWitt"]["SoilSensorChannelOrange"],
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentOrange"]))

    schedule.every(int(config["Watering"]["WaterCheckFrequencySeconds"])).seconds.do(check_for_watering)
    schedule.every(int(config["Watering"]["LeakCheckFrequencySeconds"])).seconds.do(check_for_leak)
    schedule.every(int(config["Camera"]["FrequencySeconds"])).seconds.do(snap_pic)
    schedule.every(5).minutes.do(check_pi_temp)

    while True:
        schedule.run_pending()
        time.sleep(1)

def check_for_watering():
    check_plant(lemon)
    check_plant(orange)

def check_plant(plant: Plant):
    humidity = ecowitt.get_humidity(plant)
    logging.info(f"Soil humidity of {plant.name}: {humidity}%")

    if humidity <= plant.watering_threshold:
        logging.info(f"Humidity of {plant.name} at {humidity}%, at or below threshold ({plant.watering_threshold}%)")
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
    logging.info(f"Starting watering {plant.name}")

    plant.relay.on()
    time.sleep(int(config["Watering"]["WateringDurationSeconds"]))
    plant.relay.off()

    logging.info("Watering done")

def check_for_leak():
    if ecowitt.is_leaking(config["EcoWitt"]["LeakSensorChannel"]):
        logging.warning("Leak detected!")
        hue.set_light(int(config["Hue"]["SwitchId"]), 'on', False)
        lemon.relay.off()
        orange.relay.off()
        sys.exit()

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
    logging.info(f"Picture captured and saved to {path}")

def check_pi_temp():
    logging.info(f"Pi CPU temperature: {CPUTemperature().temperature}°C")


if __name__ == '__main__':
    main()