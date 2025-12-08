import os
import requests
import json
from dotenv import load_dotenv

from config import DATA_DIR

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

def fetch_finals_results(tournament_ids):
    """
    Fetches and caches finals standings for a given tournament ID or list of IDs.
    Combines results if multiple IDs are provided.
    """
    if not isinstance(tournament_ids, list):
        tournament_ids = [tournament_ids]

    all_combined_results = []
    
    for tournament_id in tournament_ids:
        filepath = os.path.join(DATA_DIR, f"finals_standings_{tournament_id}.json")
        
        current_results = None
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                current_results = json.load(f)
        else:
            print(f"Fetching finals standings for Tournament ID: {tournament_id}...")
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

        # Only fetch data if the file doesn't exist
        if not os.path.exists(series_filepath):
            print(f"Fetching details for Series ID: {series_id}...")
            url = f"{BASE_URL}/series/{series_id}"
            params = {'includeDetails': 'true'}
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            
            series_data_raw = response.json()
            with open(series_filepath, 'w') as f:
                json.dump(series_data_raw, f, indent=4)
            print(f"Saved details for series {series_id}")
        else:
            print(f"Skipping fetch for existing Series ID: {series_id}")

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
                fetch_finals_results(finals_tournament_ids) # Fetch and cache finals results
