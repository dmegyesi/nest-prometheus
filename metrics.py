from prometheus_client import start_http_server, Summary, Gauge
import pyowm
import configparser
import os
import time
import sys
import nest


# Gauges
g = {
  'is_online': Gauge('is_online', 'Device connection status with the Nest service', ['structure', 'device']),
  'has_leaf': Gauge('has_leaf', 'Displayed when the thermostat is set to an energy-saving temperature', ['structure', 'device']),
  'target_temp': Gauge('target_temp', 'Desired temperature, in half degrees Celsius (0.5°C)', ['structure', 'device']),
  'current_temp': Gauge('current_temp', 'Temperature, measured at the device, in half degrees Celsius (0.5°C)', ['structure', 'device']),
  'humidity': Gauge('humidity', 'Humidity, in percent (%) format, measured at the device, rounded to the nearest 5%', ['structure', 'device']),
  'state': Gauge('state', 'Indicates whether HVAC system is actively heating, cooling or is off. Use this value to indicate HVAC activity state', ['structure', 'device']),
  'mode': Gauge('mode', 'Indicates HVAC system heating/cooling modes, like Heat•Cool for systems with heating and cooling capacity, or Eco Temperatures for energy savings', ['structure', 'device']),
  'time_to_target': Gauge('time_to_target', 'The time, in minutes, that it will take for the structure to reach the target temperature', ['structure', 'device']),
  
  'weather_current_temp': Gauge('weather_current_temp', 'Current temperature, in Celsius', ['city']),
  'weather_current_humidity': Gauge('weather_current_humidity', 'Current humidity, in percent (%)', ['city']),
}

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
# Decorate function with metric.
@REQUEST_TIME.time()
def polling(napi, o):
    print("%s - Polling!" % time.time())

    loc = o.get_location()
    city = loc.get_name()
    w = observation.get_weather()

    #w.get_temperature('celsius')['temp']
    for structure in napi.structures:
        for device in structure.thermostats:
            g['is_online'].labels(structure.name, device.name).set(device.online)
            g['has_leaf'].labels(structure.name, device.name).set(device.has_leaf)
            g['target_temp'].labels(structure.name, device.name).set(device.target)
            g['current_temp'].labels(structure.name, device.name).set(device.temperature)
            g['humidity'].labels(structure.name, device.name).set(device.humidity)
            g['state'].labels(structure.name, device.name).set((0 if device.hvac_state == "off" else 1))
            g['mode'].labels(structure.name, device.name).set((0 if device.mode == "off" else 1))
            g['time_to_target'].labels(structure.name, device.name).set(''.join(x for x in device.time_to_target if x.isdigit()))

    g['weather_current_temp'].labels(city).set(w.get_temperature('celsius')['temp'])
    g['weather_current_humidity'].labels(city).set(w.get_humidity())


if __name__ == '__main__':
    c = configparser.ConfigParser()
    c.read(os.path.join(os.path.abspath(os.path.dirname(__file__)),'settings.ini'))

    # Setup Nest account
    start_time = time.time()

    napi = nest.Nest(client_id=c['nest']['client_id'], client_secret=c['nest']['client_secret'], access_token_cache_file=os.path.join(os.path.abspath(os.path.dirname(__file__)),c['nest']['access_token_cache_file']))
    
    resp_time = time.time() - start_time
    sys.stderr.write("Nest API: %0.3fs\n" % resp_time)

    if napi.authorization_required:
      print("Go to " + napi.authorize_url + " to authorize, then enter PIN below")
      if sys.version_info[0] < 3:
        pin = raw_input("PIN: ")
      else:
        pin = input("PIN: ")
      napi.request_token(pin)


    # Setup OpenWeatherMap account
    start_time = time.time()

    owm = pyowm.OWM(c['owm']['owm_id'])
    observation = owm.weather_at_id(int(c['owm']['owm_city_id']))

    resp_time = time.time() - start_time
    sys.stderr.write("OpenWeatherMap API: %0.3fs\n" % resp_time)
    

    # Start up the server to expose the metrics.
    start_http_server(8000)
    sys.stdout.write("Listening on port 8000...\n")
    
    while True:
        polling(napi, observation)
        time.sleep(60)
