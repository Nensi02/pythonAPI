from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Optional, Union

import boto3
import h5py
import numpy as np
import requests
from mypy_boto3_s3.client import S3Client
from mypy_boto3_sns import SNSServiceResource
from numpy.lib.npyio import NpzFile
from numpy.typing import NDArray
from PIL import Image, TiffImagePlugin, TiffTags

from .lambda_types import SNSEvent, SNSRecord
from .model_utils import CamelCaseBaseModel
from .weather_types import ForecastResponse, IceDataEvent

logging.getLogger().setLevel(logging.INFO)
_logger = logging.getLogger(__name__)


class _EventRecordType(Enum):
    Weather = "Weather"
    Ice = "Ice"


class _ForecastTiffFiles(CamelCaseBaseModel):
    air_pressure: str
    air_temperature: str
    visibility: Optional[str]
    date: datetime


class _Listing(CamelCaseBaseModel):
    sea_temperature: str
    forecast: list[_ForecastTiffFiles]


def lambda_handler(event_obj: Any, context: Any) -> None:
    event = SNSEvent.parse_obj(event_obj)
    bucket = os.environ["AWS__S3BUCKETNAME"]
    weather_transfer_arn = os.environ["AWS__WEATHERFILECREATEDARN"]
    _logger.info("Bucket: %s", bucket)
    s3 = boto3.client("s3")

    for record in event.records:
        record_type = _get_event_record_type(record)
        message = record.sns.message

        if record_type == _EventRecordType.Weather:
            # The message is a response from the weather-service's /forecast endpoint.
            forecasts = ForecastResponse.parse_raw(message)
            _generate_weather_tiff_files(s3, bucket, forecasts, weather_transfer_arn)
        elif record_type == _EventRecordType.Ice:
            # The message is JSON-encoded WeatherPngToCloudStorage.Models.IceDataEvent.
            ice_event = IceDataEvent.parse_raw(message)
            _generate_ice_tiff_file(s3, bucket, ice_event, weather_transfer_arn)

# To get the event type whether it is weather or ice based on the event object
def _get_event_record_type(record: SNSRecord) -> _EventRecordType:
    type_attr = record.sns.message_attributes.get("Type", None)
    if type_attr is None:
        # For backwards compatability, assume Weather request.
        return _EventRecordType.Weather

    return _EventRecordType(type_attr.value)


def _generate_weather_tiff_files(
    s3: S3Client,
    bucket: str,
    forecasts: ForecastResponse,
    weather_transfer_arn: str,
) -> None:
    # Gets the analysis date from the Response body
    analysis_date = forecasts.nearest_analysis_date_relative_to_requested_date
    _logger.info("Creating TIF files for date: %s", analysis_date.isoformat())

    # Convert data without forecast (now only sea surface temperature)
    _logger.info("Single file transformation")
    # Choose the first file
    first_file = forecasts.files[0]
    _logger.info("File: %s", first_file.url)
    # Get the forecast date from the first file response
    forecast_date = first_file.response_forecast_date
    # Fetches the sea data
    with _download_forecast(first_file.url) as archive:
        # Sea surface temperature
        # Flips the Array
        sea_temp_data = _roll_and_flipud(archive["SeaSurfaceTemperature"])
        # Generates the tiff bytes from the given data and using adobe deflate
        sea_temp_tiff_bytes = _get_tiff_bytes(sea_temp_data, "tiff_adobe_deflate")
        # Generates the filename through which it needs to be stored
        sea_temp_key = _generate_tiff_object_key(analysis_date, forecast_date, "seaTemperature")
        _logger.info("Key: %s", sea_temp_key)
        # TIFF file is stored in the s3
        s3.put_object(Body=sea_temp_tiff_bytes, Bucket=bucket, Key=sea_temp_key)

    listing = _Listing(sea_temperature=sea_temp_key, forecast=[])
    for file in forecasts.files:
        _logger.info("File: %s", file.url)
        forecast_date = file.response_forecast_date

        with _download_forecast(file.url) as archive:
            # Sea surface pressure
            # Flips the Array
            pressure_data = _roll_and_flipud(archive["SeaSurfacePressure"])
            # Generates the tiff bytes from the given data and using adobe deflate
            pressure_tiff_bytes = _get_tiff_bytes(pressure_data, "tiff_adobe_deflate")
            # Generates the filename through which it needs to be stored
            pressure_key = _generate_tiff_object_key(analysis_date, forecast_date, "airPressure")
            _logger.info("Key: %s", pressure_key)
            # TIFF file is stored in the s3
            s3.put_object(Body=pressure_tiff_bytes, Bucket=bucket, Key=pressure_key)

            # Air surface temperature
            # Flips the Array
            air_temp_data = _roll_and_flipud(archive["AirTemperature"])
            # Generates the tiff bytes from the given data and using adobe deflate
            air_temp_tiff_bytes = _get_tiff_bytes(air_temp_data, "tiff_adobe_deflate")
            # Generates the filename through which it needs to be stored
            air_temp_key = _generate_tiff_object_key(analysis_date, forecast_date, "airTemperature")
            _logger.info("Key: %s", air_temp_key)
            # TIFF file is stored in the s3
            s3.put_object(Body=air_temp_tiff_bytes, Bucket=bucket, Key=air_temp_key)

            # Visibility
            visibility_key = None
            # Checks for the visibility data
            if "Visibility" in archive:
                # Flips the Array
                visibility_data = _roll_and_flipud(archive["Visibility"])
                # Generates the tiff bytes from the given data and using adobe deflate
                visibility_tiff_bytes = _get_tiff_bytes(visibility_data, "tiff_adobe_deflate")
                # Generates the filename through which it needs to be stored
                visibility_key = _generate_tiff_object_key(analysis_date, forecast_date, "visibility")
                _logger.info("Key: %s", visibility_key)
                # TIFF file is stored in the s3
                s3.put_object(Body=visibility_tiff_bytes, Bucket=bucket, Key=visibility_key)

            # Keep track of all created files
            listing.forecast.append(
                _ForecastTiffFiles(
                    air_pressure=pressure_key,
                    air_temperature=air_temp_key,
                    visibility=visibility_key,
                    date=file.response_forecast_date,
                )
            )

    # Upload listing file
    listing_key = f'list-{analysis_date.strftime("%Y%m%d%H")}.json'
    listing_json = listing.json(by_alias=True)

    # Save file for quick access on main folder
    s3.put_object(Body=listing_json, Bucket=bucket, Key="v2/" + listing_key)

    # Save file for historic analysis
    s3.put_object(Body=listing_json, Bucket=bucket, Key="v2/listings/" + listing_key)

    # Publisher publishes the message in the topic
    sns: SNSServiceResource = boto3.resource("sns")
    topic = sns.Topic(arn=weather_transfer_arn)
    weather_transfer_message = {
        "type": "tiff",
        "bucketName": bucket,
        "blobFile": "v2/" + listing_key,
    }
    topic.publish(Message=json.dumps(weather_transfer_message))

    # Clean up main v2 folder for quick access
    # Removes the latest list file and add the latest list file 
    _clean_bucket(s3, bucket)

# Fetchs the response from the URL and load it in the numpy and checks whether the instance is of Npz file or not and returns the numpy array if it is otherwise it will raise an exception.
def _download_forecast(url: str) -> NpzFile:
    # Fetchs the response
    response = requests.get(url)
    response.raise_for_status()
    # Loads the content in the buffer
    buffer = BytesIO(response.content)
    # Content of the Buffer is converted into numpy Array or dictionary of the Numpy Array
    forecast_file = np.load(buffer)
    # It is checked whether the forecast_file conatins the NpzFile instance or not then it will raise an exception
    assert isinstance(forecast_file, NpzFile)
    # returns the numpy array
    return forecast_file


def _roll_and_flipud(a: NDArray[np.float32]) -> NDArray[np.float32]:
    # Rolls the Array along vertical axis
    r = np.roll(a, a.shape[1] // 2, axis=1)
    # Flips the Array in up-down direction
    r = np.flipud(r)
    # returns the Array
    return r


def _generate_ice_tiff_file(
    s3: S3Client,
    bucket: str,
    ice_event: IceDataEvent,
    weather_transfer_arn: str,
) -> None:
    # Returns the ice data
    ice_data = _download_ice(ice_event.ice_url)
    # Flips the Array in updown direction
    ice_data = np.flipud(ice_data)
    # Generates the tiff bytes from the given data and using adobe deflate
    ice_tiff_bytes = _get_tiff_bytes(ice_data, "tiff_adobe_deflate")
    # Gets the forecast date
    ice_date_str = ice_event.ice_release.strftime("%Y%m%d")
    # Generates the filename through which it needs to be stored
    ice_key = f"v2/ice/{ice_date_str}.tif"
    _logger.info("Ice tiff file generated as object: %s/%s", bucket, ice_key)
    # TIFF file is stored in the s3
    s3.put_object(Body=ice_tiff_bytes, Bucket=bucket, Key=ice_key)

    # Publisher publishes the message in the topic
    sns: SNSServiceResource = boto3.resource("sns")
    topic = sns.Topic(arn=weather_transfer_arn)
    weather_transfer_message = {
        "type": "ice",
        "bucketName": bucket,
        "blobFile": ice_key,
    }
    topic.publish(Message=json.dumps(weather_transfer_message))


def _download_ice(url: str) -> NDArray[np.uint8]:
    # Gets the ice data
    response = requests.get(url)
    response.raise_for_status()
    with BytesIO(response.content) as raw_ice_data:
        # The h5py.File must be closed before the underlying file-like object.
        with h5py.File(raw_ice_data, "r") as hdf_file:
            sea_ice_fraction: NDArray[np.int8] = hdf_file["sea_ice_fraction"][0]
            valid_values = set(range(0, 101))
            valid_values.add(-128)
            assert set(np.unique(sea_ice_fraction)).issubset(valid_values)
            # Remap fill value to fit uint8. Treat as no ice (e.g. in case we sample on "land").
            sea_ice_fraction[sea_ice_fraction == -128] = 0
            sea_ice_fraction = sea_ice_fraction.astype(np.uint8)
            assert sea_ice_fraction.shape == (3600, 7200)

            # Return copy because we're closing the underlying BytesIO buffer.
            return sea_ice_fraction.copy()


def _get_tiff_bytes(data: NDArray[Union[np.float32, np.uint8]], compression: str = "") -> bytes:
    with BytesIO() as buffer:
        # Creates the Image from the Array
        image = Image.fromarray(data)
        planar_configuration_tag = TiffTags.lookup(TiffImagePlugin.PLANAR_CONFIGURATION)
        tiffinfo = {
            planar_configuration_tag.value: planar_configuration_tag.enum["Separate"],
        }
        # image is converted into the TIFF and compressed using adobe deflate
        image.save(buffer, format="tiff", compression=compression, tiffinfo=tiffinfo)
        # returns the bytes data
        return buffer.getvalue()


def _generate_tiff_object_key(analysis_date: datetime, forecast_date: datetime, parameter_name: str) -> str:
    analysis_date_str = analysis_date.strftime("%Y%m%d%H")
    forecast_date_str = forecast_date.strftime("%Y%m%d%H")
    # returns the AWS file name with which it needs to be saved
    return f"v2/{analysis_date_str}/{parameter_name}{forecast_date_str}.tif"

# Removes the old list file stored in the v2 folder
def _clean_bucket(s3_client: S3Client, bucket: str) -> None:
    files_to_keep = 8
    list_files = s3_client.list_objects_v2(Bucket=bucket, Prefix="v2/list-")
    if len(list_files["Contents"]) >= files_to_keep:
        for file in range(len(list_files["Contents"]) - files_to_keep):
            _logger.info("Removing: %s", list_files["Contents"][file]["Key"])
            s3_client.delete_object(Bucket=bucket, Key=list_files["Contents"][file]["Key"])
