"""Configuration constants for the logistics analytics app."""
from __future__ import annotations

WAREHOUSES = [
    "Mumbai",
    "Delhi",
    "Bangalore",
    "Chennai",
    "Kolkata",
]

PRIORITIES = ["Express", "Standard", "Economy"]

CUSTOMER_SEGMENTS = ["Enterprise", "SMB", "Individual"]

DELIVERY_OBJECTIVES = {
    "Cost": (1.0, 0.0, 0.0),
    "Time": (0.0, 1.0, 0.0),
    "Emissions": (0.0, 0.0, 1.0),
    "Balanced": (1 / 3, 1 / 3, 1 / 3),
}

DEFAULT_ROUTE_WEIGHT = (0.4, 0.35, 0.25)

MIN_STOCK_COVER_DAYS = 7

# Toggle to print debug statements across modules.
DEBUG_MODE = False
