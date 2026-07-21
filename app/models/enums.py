from __future__ import annotations
from enum import StrEnum

class Persona(StrEnum):
    FIRM = "Firm"
    DDW = "DDW"
    MDW = "MDW"
    ADVISOR = "Advisor"

class HierarchyLevel(StrEnum):
    FIRM = "Firm"
    DIVISION = "Division"
    REGION = "Region"
    MARKET = "Market"
    ADVISOR = "Advisor"

class TimePeriod(StrEnum):
    MTD = "MTD"
    QTD = "QTD"
    YTD = "YTD"
    LAST_12_MONTHS = "Last 12 Months"
    LAST_24_MONTHS = "Last 24 Months"
    LAST_36_MONTHS = "Last 36 Months"
    CUSTOM = "Custom"

class RuntimeComponentStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNCONFIGURED = "unconfigured"
    ERROR = "error"

class AdapterProvider(StrEnum):
    OPENAI = "openai"
    SMARTSDK = "smartsdk"
    MOCK = "mock"

class RecommendationStatus(StrEnum):
    GENERATED = "generated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IGNORED = "ignored"
    COMPLETED = "completed"
    EXPIRED = "expired"

class FeedbackAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    IGNORE = "ignore"
    COMPLETE = "complete"
