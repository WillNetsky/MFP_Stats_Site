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

# Minimum number of individual group games a player must have played
# to appear on the Elo ratings leaderboard.
MIN_GAMES_FOR_ELO = 50

# -- Arena Data Configuration --
# Series ID 748 (MFPinball Fall 2018) is the first season where arena data is
# correct. Before this, arena objects were renamed in-place instead of creating
# new ones, which retroactively corrupted historical machine names.
ARENA_DATA_CUTOFF_SERIES_ID = 748

# -- Caching Configuration --
# How long cached API data is considered valid, in hours.
# Data older than this will be re-fetched.
CACHE_EXPIRY_HOURS = 24
