import random
import time
import httpx
import json
import sensor_hub.config as config

URL = "http://127.0.0.1:8000/measurements"

def create_random_data() -> dict:
    data = {
        'device_id': random.choice(['esp-1', 'esp-2', 'esp-3']),
        'co2_ppm': random.randint(400, 1500),
        'temperature_c': round(random.uniform(18.0, 26.0), 2) ,
        'humidity_pct': round(random.uniform(30.0, 60.0), 2)
    }

    return data

def run_simulator():
    while True:

        data = json.dumps(create_random_data())
        settings = config.get_settings()

        try:
            response = httpx.post(
                URL,
                content= data,
                headers= {'Content-Type': 'application/json',
                          'X-Api-Key': settings.api_key.get_secret_value()}
                )
            
            print(response)

        except httpx.ConnectError:
            print('Server not available ...')
             
        time.sleep(2)

if __name__ == '__main__':

    try:
        run_simulator()

    except KeyboardInterrupt:
        print('Stopping ...')