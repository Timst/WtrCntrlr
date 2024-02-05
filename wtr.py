import json
import sys
import schedule
import logging
import time
import configparser
from glob import glob
from PIL import Image
from pyemvue import PyEmVue, device
from gpiozero import LED, CPUTemperature
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path

from plant import Plant
from ecowitt import LocalEcowitt, NetEcowitt

CONFIG_FILE = "config.ini"
EMPORIA_KEY_FILE = "emporia_keys.json"
config = None

ecowitt = None

vue: PyEmVue = None
heater_plug: device  = None
lamp_plug: device  = None
humidifier_plug: device  = None

camera: Picamera2 = None
camera_start_time: datetime = None
camera_end_time: datetime = None

lemon: Plant = None
orange: Plant = None
lime: Plant = None

def main():
    global config
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    logging.basicConfig(
        level=logging.getLevelName(config["System"]["Logging"].upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("wtr.log"),
            logging.StreamHandler()
        ]
    )

    global ecowitt
    if config["EcoWitt"]["Mode"] == "Local":
        logging.info("Creating Ecowitt client in local mode")
        ecowitt = LocalEcowitt(config["EcoWitt"]["IP"])
    elif config["EcoWitt"]["Mode"] == "Net":
        logging.info("Creating Ecowitt client in net mode")
        ecowitt = NetEcowitt(
            app_key=config["EcoWitt"]["AppKey"],
            api_key=config["EcoWitt"]["ApiKey"],
            device_mac=config["EcoWitt"]["DeviceMac"])

    global vue, heater_plug, lamp_plug, humidifier_plug
    vue = PyEmVue()
    with open(EMPORIA_KEY_FILE, encoding="us-ascii") as f:
        emporia_keys = json.load(f)

    if vue.login(id_token=emporia_keys['id_token'],
        access_token=emporia_keys['access_token'],
        refresh_token=emporia_keys['refresh_token'],
        token_storage_file=EMPORIA_KEY_FILE):

        devices = vue.get_devices()

        heater_plug = next(filter(lambda x: x.manufacturer_id == config["Emporia"]["HeaterPlugId"], devices)).outlet
        lamp_plug = next(filter(lambda x: x.manufacturer_id == config["Emporia"]["LampPlugId"], devices)).outlet
        humidifier_plug = next(filter(lambda x: x.manufacturer_id == config["Emporia"]["HumidifierPlugId"], devices)).outlet
    else:
        logging.error("Couldn't login to Emporia, check emporia_keys.json file")

    global camera
    if config["Camera"]["Enable"] == "True":
        logging.info("Camera enabled")
        Path(config["Camera"]["Folder"]).mkdir(exist_ok=True)

        camera = Picamera2()
        camera_config = camera.create_still_configuration()
        camera.configure(camera_config)

        if config["Camera"]["Crop"] == "True":
            camera.set_controls({"ScalerCrop":(
                int(config["Camera"]["X"]),
                int(config["Camera"]["Y"]),
                int(config["Camera"]["Width"]),
                int(config["Camera"]["Height"]),
            )})

        if config["Camera"]["TimeLimit"] == "True":
            global camera_start_time, camera_end_time
            camera_start_time = datetime.strptime(config["Camera"]["StartTime"], "%H:%M:%S")
            camera_end_time = datetime.strptime(config["Camera"]["EndTime"], "%H:%M:%S")

        camera.start()

    global lemon, orange, lime
    lemon = Plant(name= "Lemon",
                  relay= LED(int(config["Relay"]["GpioPinLemon"])),
                  sensor_channel=config["EcoWitt"]["SoilSensorChannelLemon"],
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentLemon"]))

    orange = Plant(name= "Orange",
                  relay= LED(int(config["Relay"]["GpioPinOrange"])),
                  sensor_channel=config["EcoWitt"]["SoilSensorChannelOrange"],
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentOrange"]))

    lime = Plant(name= "Lime",
                  relay= LED(int(config["Relay"]["GpioPinLime"])),
                  sensor_channel=config["EcoWitt"]["SoilSensorChannelLime"],
                  watering_threshold=int(config["Watering"]["HumidityThresholdPercentLime"]))

    schedule.every(int(config["Watering"]["WaterCheckFrequencySeconds"])).seconds.do(check_for_watering)
    schedule.every(int(config["Watering"]["LeakCheckFrequencySeconds"])).seconds.do(check_for_leak)
    schedule.every(5).minutes.do(check_pi_temp)
    if camera is not None:
        schedule.every(int(config["Camera"]["FrequencySeconds"])).seconds.do(snap_pic)

    while True:
        schedule.run_pending()
        time.sleep(1)

def check_for_watering():
    check_plant(lemon)
    check_plant(orange)
    check_plant(lime)

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
        logging.fatal("Leak detected!")

        lemon.relay.off()
        orange.relay.off()

        vue.update_outlet(heater_plug, on=False)
        vue.update_outlet(lamp_plug, on=False)
        vue.update_outlet(humidifier_plug, on=False)

        sys.exit()

def snap_pic():
    if config["Camera"]["TimeLimit"] == "True":
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
    make_gif()

def make_gif():
    frames = [Image.open(image) for image in glob(f"{config['Camera']['Folder']}/*.png")]
    if len(frames) > 0:
        frame_one = frames[0]
        frame_one.save("timelapse.gif",
                       format="GIF",
                       append_images=frames,
                       save_all=True,
                       duration=100,
                       loop=0)
        logging.info("Generated timelapse")

def check_pi_temp():
    logging.info(f"Pi CPU temperature: {CPUTemperature().temperature}°C")


if __name__ == '__main__':
    main()