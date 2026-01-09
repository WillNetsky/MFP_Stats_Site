# config.py

# -- File/Directory Paths --
DATA_DIR = "data"
OUTPUT_DIR = "output"
TEMPLATES_DIR = "templates"
STATIC_DIR = "static"

# -- Series Configuration --
# Series to exclude from all processing
EXCLUDED_SERIES_NAMES = [
    "The Beforefore Times",
    "Tuesday Night Strikes Winter 2020",
    "MFPinball 2019 Spring Season  (clone)"
]

# Variations of the MFLadies Pinball league name
MFLADIES_LEAGUE_NAMES = [
    "Monterey Flipper Ladies Pinball",
    "MFLadies",
    "MFLPinball",
    "MF Ladies Pinball"
]

# -- Leaderboard Configuration --
# Minimum number of weeks a player must have played in two consecutive seasons
# to be eligible for the "Most Improved Player" leaderboard.
MIN_WEEKS_FOR_IMPROVEMENT = 5

# -- Caching Configuration --
# How long cached API data is considered valid, in hours.
# Data older than this will be re-fetched.
CACHE_EXPIRY_HOURS = 24
