from fastapi import FastAPI, Request
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from typing import Any
from datetime import timedelta
from pymongo.collection import Collection
from io import BytesIO
from PIL import Image
import regex
import re
import requests
import datetime
import pydantic
import motor.motor_asyncio
import pytz
import matplotlib.pyplot as plt
import datetime
import regex
import pytz
from datetime import datetime, timedelta

app = FastAPI()


origins = [
    "https://simple-smart-hub-client.netlify.app",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
pydantic.json.ENCODERS_BY_TYPE[ObjectId] = str

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb+srv://smasher1428:xCs61MnkOLBZI5Uz@cluster0.nubqjnu.mongodb.net/?retryWrites=true&w=majority")
db = client.iot_platform
sensor_readings_col = db['sensor_readings']
data_col = db['data']

# Initialize Nominatim API
geolocator = Nominatim(user_agent="MyApp")
location = geolocator.geocode("Hyderabad")



regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')

def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)

async def update_sensor_data(sensor_readings_col, output):
    # update the database with the new sensor data
    obj = await sensor_readings_col.find().sort('_id', -1).limit(1).to_list(1)
    if obj:
        await sensor_readings_col.update_one({"_id": obj[0]["_id"]}, {"$set": output})
        new_obj = await sensor_readings_col.find_one({"_id": obj[0]["_id"]})
    else:
        new = await sensor_readings_col.insert_one(output)
        new_obj = await sensor_readings_col.find_one({"_id": new.inserted_id})
    return new_obj

def get_sunset_time():
    user_latitude = location.latitude
    user_longitude = location.longitude
    sunset_api_endpoint = f'https://api.sunrise-sunset.org/json?lat={user_latitude}&lng={user_longitude}'
    sunset_api_response = requests.get(sunset_api_endpoint)
    sunset_api_data = sunset_api_response.json()
    sunset_time = datetime.strptime(sunset_api_data['results']['sunset'], '%I:%M:%S %p').time()
    return datetime.strptime(str(sunset_time),"%H:%M:%S") + parse_time("5h")

@app.get('/graph')
async def get_graph(request: Request):
    size = int(request.query_params.get('size', 10))
    readings = await data_col.find().sort('_id', -1).limit(size).to_list(size)
    data_reading = []
    for reading in readings:
        temperature = reading.get("temperature")
        presence = reading.get("presence")
        current_time = reading.get("current_time")

        data_reading.append({
            "temperature": temperature,
            "presence": presence,
            "datetime": current_time
        })

    return data_reading

sensor_readings_col: Collection

@app.put('/settings')
async def update_sensor_readings(request: Request):
    state = await request.json()
    user_temp = state["user_temp"]
    user_light = state["user_light"]
    light_time_off = state["light_duration"]

    # calculate the light-off time based on theuser input
    if user_light == "sunset":
        user_light_scr = get_sunset_time()
    else:
        user_light_scr = datetime.strptime(user_light, "%H:%M:%S")
        
    new_user_light = user_light_scr + parse_time(light_time_off)

    # create a dictionary with the output values
    output = {
        "user_temp": user_temp,
        "user_light": str(user_light_scr.time()),
        "light_time_off": str(new_user_light.time())
    }

    # call the update_sensor_data function
    new_obj = await update_sensor_data(sensor_readings_col, output)

    return new_obj

@app.post("/temperature")
async def update_temperature(request: Request):
    condition = await request.json()

    # get the latest sensor readings
    latest_reading = await sensor_readings_col.find().sort('_id', -1).limit(1).to_list(1)

    if latest_reading:
        user_temp = latest_reading[0]["user_temp"]
        user_light = datetime.strptime(latest_reading[0]["user_light"], "%H:%M:%S")
        time_off = datetime.strptime(latest_reading[0]["light_time_off"], "%H:%M:%S")
    else:
        user_temp = 10
        user_light = datetime.strptime("18:00:00", "%H:%M:%S")
        time_off = datetime.strptime("20:00:00", "%H:%M:%S")

    now_time = datetime.now(pytz.timezone('Jamaica')).time()
    current_time = datetime.strptime(str(now_time), "%H:%M:%S.%f")

    # calculate the light and fan conditions based on the sensor readings
    condition["light"] = ((current_time < user_light) and (current_time < time_off) and (condition["presence"] == 1))
    condition["fan"] = (float(condition["temperature"]) >= user_temp) and (condition["presence"] == 1)
    condition["current_time"] = str(datetime.now())

    # insert thenew sensor readings into the database
    new_settings = await data_col.insert_one(condition)
    new_obj = await data_col.find_one({"_id": new_settings.inserted_id})

    return new_obj

@app.get("/state")
async def get_state():
   # retrieve the last sensor reading from the database
   last_reading = await data_col.find().sort('_id', -1).limit(1).to_list(1)  
   if not last_reading:
       return {
           "presence": False,
           "fan": False,
           "light": False,
           "current_time": datetime.now()
       }
   return last_reading[0]