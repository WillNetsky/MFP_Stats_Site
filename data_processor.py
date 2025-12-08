import os
import json
import re

from config import DATA_DIR

def load_all_series_data(excluded_series_names):
    """Loads all series data from the JSON files in the data directory."""
    all_series_data = []
    if not os.path.exists(DATA_DIR):
        return all_series_data
        
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("series_") and filename.endswith(".json"):
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, 'r') as f:
                series_data_raw = json.load(f)
                
                # --- ADD THIS DEBUG PRINT STATEMENT ---
                current_series_name = series_data_raw['data']['name']
                print(f"DEBUG: Checking series '{current_series_name}' (ID: {series_data_raw['data']['seriesId']}) against excluded list: {excluded_series_names}")
                # --- END DEBUG PRINT STATEMENT ---

                # Also filter excluded series during loading, in case they were fetched previously
                if current_series_name in excluded_series_names:
                    print(f"Skipping excluded series during load: {current_series_name} (ID: {series_data_raw['data']['seriesId']})")
                    continue
                all_series_data.append(series_data_raw)
    return all_series_data

def load_finals_mapping():
    """Loads the finals mapping from finals_mapping.json."""
    filepath = os.path.join(DATA_DIR, 'finals_mapping.json')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def parse_series_name(series_name):
    """Parses a series name into Year, Season, and League components."""
    year = "N/A"
    season_name = "N/A"
    league_name = "Other"
    
    original_name = series_name # Keep original for parsing

    # Extract Year (assuming 4 digits)
    year_match = re.search(r'(\d{4})', series_name)
    if year_match:
        year = year_match.group(1)
        # Remove year from series_name to simplify season/league parsing
        series_name_without_year = series_name.replace(year, '').strip()
    else:
        series_name_without_year = series_name

    # Determine League
    if "MFPinball" in original_name or "MFP" in original_name:
        league_name = "MFPinball"
    elif "Monterey Flipper Ladies Pinball" in original_name or "MFLadies" in original_name:
        league_name = "MFLadies Pinball"
    
    # Extract Season (remaining significant words)
    season_keywords = ["Fall", "Summer", "Winter", "Spring"]
    for keyword in season_keywords:
        if keyword in series_name_without_year:
            season_name = keyword
            break
    
    # If season_name is still N/A, try to infer from common patterns or leave as N/A
    if season_name == "N/A":
        # Example: "MFPinball 2023 League" -> season_name = "League"
        if "League" in series_name_without_year:
            season_name = "League"
        elif "Season" in series_name_without_year:
            season_name = "Season"

    return year, season_name, league_name

def apply_year_corrections_to_seasons_list(seasons_list):
    """Applies specific year correction logic to a list of season entries."""
    # Sort ascending by seriesId to ensure consistent "first two" for 2018
    seasons_list.sort(key=lambda x: x['seriesId'])
    
    mflp_2018_assigned = 0
    for season in seasons_list:
        # Specific correction for MFPinball season ID 5198
        if season['seriesId'] == 5198 and season['league_name'] == "MFPinball":
            season['year'] = "2026"
            continue # Skip general N/A logic for this season

        if season['year'] == "N/A":
            if season['league_name'] == "MFLadies Pinball":
                if mflp_2018_assigned < 2:
                    season['year'] = "2018"
                    mflp_2018_assigned += 1
                else:
                    season['year'] = "2024"

            elif season['league_name'] == "MFPinball":
                season['year'] = "2024" # Default for MFPinball if not specifically handled
            else: # Default for other leagues if year is N/A
                season['year'] = "2024"
    
    # Re-sort for display
    seasons_list.sort(key=lambda x: x['seriesId'], reverse=True)
    return seasons_list
