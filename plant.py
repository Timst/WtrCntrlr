from dataclasses import dataclass
from gpiozero import LED

@dataclass
class Plant:
    name: str
    relay: LED
    sensor_id: str
    rest_active: bool
    rest_period: int
    
    
def __init__(self, name: str, relay: LED, sensor_id: str):
    self.name = name
    self.relay = relay
    self.sensor_id = sensor_id
    self.rest_active = False
    self.rest_period = 0