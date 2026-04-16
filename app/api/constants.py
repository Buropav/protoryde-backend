import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

EXCLUSIONS_VERSION = "v1.0.0"
EXCLUSIONS = [
    "Health, injury, or accident of any kind",
    "Vehicle damage, repair, or maintenance",
    "Income loss due to personal decision not to work",
    "Disruptions caused by war, armed conflict, or military operations",
    "Pandemic or epidemic declared events",
    "Nuclear events or radiation incidents",
    "Disruptions caused by rider platform violations or account suspension",
    "Pre-existing platform bans or rating-based deactivations",
    "Income loss unrelated to an active parametric trigger",
    "Civil unrest or protests the rider participated in",
]
