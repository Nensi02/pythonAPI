# Adapted from https://github.com/aws/aws-lambda-dotnet/blob/master/Libraries/src/Amazon.Lambda.SNSEvents/SNSEvent.cs
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .model_utils import TitleCaseBaseModel


class SNSMessageAttribute(TitleCaseBaseModel):
    type: str  # noqa: A003
    value: str


class SNSMessage(TitleCaseBaseModel):
    message: str
    message_attributes: dict[str, SNSMessageAttribute]
    message_id: str
    signature: Optional[str]
    signature_version: Optional[str]
    signing_cert_url: Optional[str]
    subject: Optional[str]
    timestamp: datetime
    topic_arn: Optional[str]
    type: str  # noqa: A003
    unsubscribe_url: Optional[str]


class SNSRecord(TitleCaseBaseModel):
    event_source: str
    event_subscription_arn: str
    event_version: str
    sns: SNSMessage


class SNSEvent(TitleCaseBaseModel):
    records: list[SNSRecord]
