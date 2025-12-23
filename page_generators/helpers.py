import json
from markupsafe import escape

# --- Jinja2 Custom Filters ---
def score_color_filter(score):
    """
    Jinja2 filter to color-code scores based on value.
    5 (worst) -> Red, 20 -> White, 34 -> Green, 35 -> Gold.
    'N/A' or None -> Blank.
    
    Returns a span with a data-score attribute so CSS can handle theming.
    """
    if score is None or score == 'N/A' or score == '-':
        return "" # Blank out if no score

    try:
        score_val = float(score)
    except ValueError:
        return str(score) # Return as is if not a number

    # Instead of inline styles, we return a span with a class and data attribute
    # This allows CSS to handle the coloring for both light and dark modes
    return f'<span class="score-badge" data-score="{score_val}">{int(score_val) if score_val == int(score_val) else score_val}</span>'

def format_number_filter(value):
    """
    Jinja2 filter to format a number as an integer if it's a whole number,
    otherwise as a float rounded to 2 decimal places.
    """
    if value is None or value == 'N/A':
        return value
    try:
        num = float(value)
        if num == int(num):
            return int(num)
        else:
            return round(num, 2)
    except (ValueError, TypeError):
        return value

def get_qualification_threshold(year_str, season_name):
    """
    Determines the minimum number of weeks a player must play to qualify for a season.
    - 6 weeks for Winter 2022 and beyond.
    - 5 weeks before Winter 2022.
    """
    if year_str == "N/A":
        return 5 # Conservative default if year is unknown

    year = int(year_str)
    
    # Define the cutoff point: Winter 2022
    cutoff_year = 2022
    cutoff_season = "Winter"
    
    # Define a rough chronological order for seasons within a year for comparison
    # This assumes a typical yearly cycle. Adjust if your league's seasons are different.
    # "League" and "Season" are treated as general season names that would likely fall after specific named seasons.
    season_order_map = {
        "Winter": 0,
        "Spring": 1,
        "Summer": 2,
        "Fall": 3,
        "League": 4, 
        "Season": 5
    }

    if year > cutoff_year:
        return 6
    elif year == cutoff_year:
        current_season_rank = season_order_map.get(season_name, -1)
        cutoff_season_rank = season_order_map.get(cutoff_season, -1)
        
        if current_season_rank != -1 and cutoff_season_rank != -1:
            if current_season_rank >= cutoff_season_rank:
                return 6
            else: # e.g., Fall 2022 (rank 3) is before Winter 2022 (rank 0) in this map
                return 5
        else:
            # If season name is not in our map for 2022, default to 6 weeks for safety
            # This handles cases like "2022 League" which should probably be 6 weeks.
            return 6
    else: # year < cutoff_year
        return 5

# Custom filter for safe JSON embedding in HTML attributes
def json_attribute_filter(obj):
    return escape(json.dumps(obj))
