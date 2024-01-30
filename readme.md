# 🆆🆃🆁🅲🅽🆃🆁🅻🆁

WtrCntrlr is a system to automatically water the orange tree that I'm growing in my bathtub (I'm very bored). This is meant to run on a RaspberryPi, as I'm making use of the GPIO pin to control a [5V relay](https://www.amazon.com/dp/B08PP2LV97), which in turn actuates a [12V solenoid valve](https://www.amazon.com/dp/B07NWCRM75) which I connected to my shower inlet with some PEX pipe (listen, I never said this was a good idea or that you should do this).

## Integrations

Besides the GPIO, it interfaces with:
- Soil humidity and water leak sensors from [Ecowitt](https://www.ecowitt.com/), a cheap chinese brand of weather/climate sensors
- Philips Hue, because I have one of their [smart plug](https://www.amazon.com/Philips-Hue-Lights-Bluetooth-Compatible/dp/B07XD578LD), on which the [LED grow light](https://www.amazon.com/dp/B07PLY1WKK) and space heater (no link, I got the cheapest thing at Lowe's) run on a schedule. Here I use it as an emergency stop if a leak is detected.

## Installation
If you want to make this run at home (why?), you'll simply need to rename the example.ini config file and put the appropriate IDs and keys. Ecowitt credentials can be created at ecowitt.net. On the first run you'll also need to press the pairing button on your Hue Bridge and uncomment the line that creates the connection. It should work out of the box after that.

## Future plans

Instead of the Hue plug, I'm going to switch to [Emporia plugs](https://www.amazon.com/Energy-Monitoring-Continuous-Certified-Package/dp/B0CLVRZ2QL), firstly because I'm already using their whole-house monitoring system, and secondly as a way to specifically monitor how much energy I'm burning on this dumb idea, and to be able to control each device individually.

Currently this only controls one watering device, but I actually have both an orange and a lemon tree in my bathtub (with room to spare!). If this works, I'll update the code to support multiple devices.

I also got one of these little PiCamera modules. I might add logic to take a pic every hour and do a timelapse thing.

