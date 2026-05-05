"""Constants for the SettleUp integration."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "settleup"

UPDATE_INTERVAL_SECONDS = 300
DEFAULT_SCAN_INTERVAL   = UPDATE_INTERVAL_SECONDS

CONF_EMAIL   = "email"
CONF_API_KEY = "api_key"

FIREBASE_API_KEY_SANDBOX = ""
FIREBASE_AUTH_URL    = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token?key={api_key}"

SANDBOX_DB = "https://settle-up-sandbox.firebaseio.com"
LIVE_DB    = "https://settle-up-live.firebaseio.com"


TRANSACTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema",
    "title": "SettleUp Transaction Schema",
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "currencyCode": {
            "type": "string",
            "minLength": 3,
            "maxLength": 3,
            "pattern": "[A-Z]{3}",
        },
        "dateTime": {"type": "integer"},
        "fixedExchangeRate": {"type": "boolean"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {
                        "pattern": r"^\d+(?:\.\d+)?$",
                        "type": "string",
                    },
                    "forWhom": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "memberId": {"type": "string"},
                                "weight": {
                                    "pattern": r"^\d+(?:\.\d+)?$",
                                    "type": "string",
                                },
                            },
                            "required": ["memberId", "weight"],
                        },
                        "minItems": 0,
                    },
                },
                "required": ["amount", "forWhom"],
            },
            "minItems": 0,
        },
        "purpose": {"type": "string"},
        "type": {"type": "string"},
        "whoPaid": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "memberId": {"type": "string"},
                    "weight": {"type": "string"},
                },
                "required": ["memberId", "weight"],
            },
            "minItems": 0,
        },
    },
    "required": [
        "category",
        "currencyCode",
        "dateTime",
        "fixedExchangeRate",
        "items",
        "purpose",
        "type",
        "whoPaid",
    ],
}
