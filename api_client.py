import os
import requests
import json
from dotenv import load_dotenv
import time # Import time module

from config import DATA_DIR, CACHE_EXPIRY_HOURS

load_dotenv()

# Matchplay API configuration
API_KEY = os.getenv("MATCHPLAY_API_KEY")
USER_ID = os.getenv("USER_ID")
BASE_URL = "https://app.matchplay.events/api"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def is_cache_stale(filepath):
    """Checks if a cached file is older than CACHE_EXPIRY_HOURS."""
    if not os.path.exists(filepath):
        return True
    file_mod_time = os.path.getmtime(filepath)
    current_time = time.time()
    return (current_time - file_mod_time) > (CACHE_EXPIRY_HOURS * 3600) # 3600 seconds in an hour

def get_series_by_owner(user_id, status=None):
    """
    Fetches series from the Matchplay API for a specific owner.
    This function handles pagination to retrieve all series.
    """
    print(f"--- Fetching series for owner ID: {user_id} ---")
    url = f"{BASE_URL}/series"
    params = {'owner': user_id}
    if status:
        params['status'] = status
        print(f"--- Filtering by status: {status} ---")

    all_series = []
    page = 1
    while True:
        params['page'] = page
        print(f"Fetching page {page}...")
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('data'):
            all_series.extend(data['data'])
            page += 1
        else:
            break
    
    return all_series

def fetch_finals_results(tournament_ids, series_status='active'):
    """
    Fetches and caches finals standings for a given tournament ID or list of IDs.
    Combines results if multiple IDs are provided.
    The series_status is used to determine if cache staleness should be checked.
    """
    if not isinstance(tournament_ids, list):
        tournament_ids = [tournament_ids]

    all_combined_results = []
    
    for tournament_id in tournament_ids:
        filepath = os.path.join(DATA_DIR, f"finals_standings_{tournament_id}.json")
        
        current_results = None
        should_fetch = False

        if series_status == 'completed':
            if not os.path.exists(filepath):
                should_fetch = True
            else:
                print(f"Using permanently cached finals standings for Tournament ID: {tournament_id} (completed series)...")
                with open(filepath, 'r') as f:
                    current_results = json.load(f)
        else: # active or upcoming series
            if not os.path.exists(filepath) or is_cache_stale(filepath):
                should_fetch = True
            else:
                print(f"Using cached finals standings for Tournament ID: {tournament_id}...")
                with open(filepath, 'r') as f:
                    current_results = json.load(f)

        if should_fetch:
            print(f"Fetching finals standings for Tournament ID: {tournament_id} (cache stale/not found or completed series)...")
            url = f"{BASE_URL}/tournaments/{tournament_id}/standings" # Corrected endpoint
            try:
                response = requests.get(url, headers=HEADERS)
                response.raise_for_status()
                current_results = response.json()
                with open(filepath, 'w') as f:
                    json.dump(current_results, f, indent=4)
                print(f"Saved finals standings for tournament {tournament_id}")
            except requests.exceptions.RequestException as e:
                print(f"Error fetching finals standings for tournament {tournament_id}: {e}")
                current_results = None
        
        if current_results:
            all_combined_results.extend(current_results)
    
    # Sort the combined results by position
    if all_combined_results:
        all_combined_results.sort(key=lambda x: x['position'])
    
    return all_combined_results

def fetch_data(excluded_series_names, finals_mapping, parse_series_name_func):
    """Fetches all necessary data from the Matchplay API."""
    print("Fetching data from Matchplay API...")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    series_list = get_series_by_owner(USER_ID)
    
    for series in series_list:
        if series['name'] in excluded_series_names:
            print(f"Skipping excluded series: {series['name']} (ID: {series['seriesId']})")
            continue

        series_id = series['seriesId']
        series_filepath = os.path.join(DATA_DIR, f"series_{series_id}.json")

        should_fetch_series = False
        if series['status'] == 'completed':
            if not os.path.exists(series_filepath):
                should_fetch_series = True
            else:
                print(f"Using permanently cached details for Series ID: {series_id} (completed series)...")
                series_data_raw = json.load(open(series_filepath, 'r'))
        else: # active or upcoming series
            if not os.path.exists(series_filepath) or is_cache_stale(series_filepath):
                should_fetch_series = True
            else:
                print(f"Using cached details for Series ID: {series_id}...")
                series_data_raw = json.load(open(series_filepath, 'r'))

        if should_fetch_series:
            print(f"Fetching details for Series ID: {series_id} (cache stale/not found or completed series)...")
            url = f"{BASE_URL}/series/{series_id}"
            params = {'includeDetails': 'true'}
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            
            series_data_raw = response.json()
            with open(series_filepath, 'w') as f:
                json.dump(series_data_raw, f, indent=4)
            print(f"Saved details for series {series_id}")

        # After saving series data, check if it has associated finals in the mapping
        year, season_name_parsed, league_name_parsed = parse_series_name_func(series['name'])
        
        # Apply year correction logic to the parsed year for finals lookup
        # This is a simplified version for fetch_data; full correction happens in generate_pages
        corrected_year = year
        if corrected_year == "N/A":
            if "MFLadies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
                corrected_year = "2024" # Assume 2024 for lookup if not explicitly found
            elif "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
                corrected_year = "2024"

        if league_name_parsed in finals_mapping and corrected_year != "N/A" and season_name_parsed != "N/A":
            key = f"{season_name_parsed} {corrected_year}"
            finals_tournament_ids = finals_mapping[league_name_parsed].get(key)
            if finals_tournament_ids:
                # Pass the series status to fetch_finals_results
                fetch_finals_results(finals_tournament_ids, series_status=series['status'])
