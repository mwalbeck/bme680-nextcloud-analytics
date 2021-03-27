#!/usr/bin/env python3

import json
import time
import sys
import os
from statistics import mean
from datetime import datetime

import bme680
import requests


def main():
    try:
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
    except IOError:
        sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

    with open(
        os.getenv("HOME") + "/.config/bme680-nextcloud-analytics.json"
    ) as config_file:
        try:
            config = json.load(config_file)
        except ValueError:
            sys.exit("Invalid json in config file.")

    if "polling_rate" not in config:
        config["polling_rate"] = 1

    if "upload_frequency" not in config:
        config["upload_frequency"] = 60

    if "temp_offset" in config:
        sensor.set_temp_offset(config["temp_offset"])

    sensor.set_humidity_oversample(bme680.OS_2X)
    sensor.set_pressure_oversample(bme680.OS_4X)
    sensor.set_temperature_oversample(bme680.OS_8X)
    sensor.set_filter(bme680.FILTER_SIZE_3)

    if "enable_gas_sensor" in config and config["enable_gas_sensor"]:
        sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
        sensor.set_gas_heater_temperature(320)
        sensor.set_gas_heater_duration(150)
        sensor.select_gas_heater_profile(0)

    while True:
        sensor_data = monitor(
            sensor, config["polling_rate"], config["upload_frequency"]
        )
        upload(sensor_data, config["user"], config["password"], config["url"])


def monitor(sensor, polling_rate, upload_frequency):
    sensor_data = {"temperature": [], "pressure": [], "humidity": []}

    next_time = time.time() + polling_rate
    while len(sensor_data["temperature"]) != upload_frequency / polling_rate:
        time.sleep(max(0, next_time - time.time()))
        if sensor.get_sensor_data():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output = "{0},{1:.2f} C,{2:.2f} hPa,{3:.3f} %RH".format(
                timestamp,
                sensor.data.temperature,
                sensor.data.pressure,
                sensor.data.humidity,
            )
            sensor_data["temperature"].append(sensor.data.temperature)
            sensor_data["pressure"].append(sensor.data.pressure)
            sensor_data["humidity"].append(sensor.data.humidity)
            print(output)

        next_time += (
            time.time() - next_time
        ) // polling_rate * polling_rate + polling_rate

    sensor_data["timestamp"] = timestamp
    return sensor_data


def upload(sensor_data, user, password, url):
    headers = {"Content-Type": "application/json"}

    payload = {
        "data": [
            {
                "dimension1": "Temperature",
                "dimension2": sensor_data["timestamp"],
                "value": mean(sensor_data["temperature"]),
            },
            {
                "dimension1": "Pressure",
                "dimension2": sensor_data["timestamp"],
                "value": mean(sensor_data["pressure"]),
            },
            {
                "dimension1": "Humidity",
                "dimension2": sensor_data["timestamp"],
                "value": mean(sensor_data["humidity"]),
            },
        ]
    }

    requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=10,
        auth=(user, password),
    )


if __name__ == "__main__":
    main()
