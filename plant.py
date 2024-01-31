from dataclasses import dataclass
from gpiozero import LED

@dataclass
class Plant:
    name: str
    relay: LED
    sensor_id: str
    watering_threshold: int
    rest_active: bool
    rest_period: int
      
    def __init__(self, name: str, relay: LED, sensor_id: str, watering_threshold: int):
        self.name = name
        self.relay = relay
        self.sensor_id = sensor_id
        self.watering_threshold = watering_threshold
        self.rest_active = False
        self.rest_period = 0