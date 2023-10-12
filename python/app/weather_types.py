from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .model_utils import TitleCaseBaseModel


class ForecastFile(BaseModel):
    file_name: str
    requested_forecast_date: datetime
    response_analysis_date: datetime
    response_forecast_date: datetime
    url: str


class ForecastResponse(BaseModel):
    """
    Models the weather-service's /forecast endpoint response.
    """

    files: list[ForecastFile]
    nearest_analysis_date_relative_to_requested_date: datetime


class IceDataEvent(TitleCaseBaseModel):
    ice_url: str
    ice_release: datetime
