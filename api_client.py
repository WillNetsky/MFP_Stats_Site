import os
import requests
import json
from dotenv import load_dotenv
import time

from config import DATA_DIR, CACHE_EXPIRY_HOURS
from page_generators.caching import memoize_by_first_arg

load_dotenv()

API_KEY = os.getenv("MATCHPLAY_API_KEY")
USER_ID = os.getenv("USER_ID")
BASE_URL = "https://app.matchplay.events/api"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def is_cache_stale(filepath):
    if not os.path.exists(filepath):
        return True
    file_mod_time = os.path.getmtime(filepath)
    current_time = time.time()
    return (current_time - file_mod_time) > (CACHE_EXPIRY_HOURS * 3600)

def get_series_by_owner(user_id, status=None):
    print(f"--- Fetching series for owner ID: {user_id} ---")
    url = f"{BASE_URL}/series"
    params = {'owner': user_id}
    if status:
        params['status'] = status
    all_series = []
    page = 1
    while True:
        params['page'] = page
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('data'):
            all_series.extend(data['data'])
            page += 1
        else:
            break
    return all_series

@memoize_by_first_arg
def fetch_finals_results(tournament_ids, series_status='active'):
    if not isinstance(tournament_ids, list):
        tournament_ids = [tournament_ids]
    all_combined_results = []
    for tournament_id in tournament_ids:
        filepath = os.path.join(DATA_DIR, f"finals_standings_{tournament_id}.json")
        if not is_cache_stale(filepath) and os.path.exists(filepath):
            print(f"Using cached finals standings for Tournament ID: {tournament_id}...")
            with open(filepath, 'r') as f:
                all_combined_results.extend(json.load(f))
            continue
        
        print(f"Fetching finals standings for Tournament ID: {tournament_id}...")
        url = f"{BASE_URL}/tournaments/{tournament_id}/standings"
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            current_results = response.json()
            with open(filepath, 'w') as f:
                json.dump(current_results, f, indent=4)
            all_combined_results.extend(current_results)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching finals standings for tournament {tournament_id}: {e}")
    
    if all_combined_results:
        all_combined_results.sort(key=lambda x: x['position'])
    return all_combined_results

@memoize_by_first_arg
def fetch_tournament_games(tournament_id, series_status='active'):
    filepath = os.path.join(DATA_DIR, f"tournament_games_{tournament_id}.json")
    if not is_cache_stale(filepath) and os.path.exists(filepath):
        print(f"Using cached game data for Tournament ID: {tournament_id}...")
        with open(filepath, 'r') as f:
            return json.load(f)

    print(f"Fetching game data for Tournament ID: {tournament_id}...")
    url = f"{BASE_URL}/tournaments/{tournament_id}/games"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        games_data = response.json()
        
        # After fetching, also fetch tournament details to embed arena names
        tournament_details = fetch_tournament_details(tournament_id, series_status)
        if tournament_details and 'data' in tournament_details and 'arenas' in tournament_details['data']:
            arena_map = {arena['arenaId']: arena for arena in tournament_details['data']['arenas']}
            if 'data' in games_data:
                for game in games_data['data']:
                    if game.get('arenaId') and game['arenaId'] in arena_map:
                        game['arena'] = arena_map[game['arenaId']]
        
        with open(filepath, 'w') as f:
            json.dump(games_data, f, indent=4)
        print(f"Saved game data for tournament {tournament_id}")
        return games_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching game data for tournament {tournament_id}: {e}")
        return None

@memoize_by_first_arg
def fetch_tournament_details(tournament_id, series_status='active'):
    filepath = os.path.join(DATA_DIR, f"tournament_details_{tournament_id}.json")
    if not is_cache_stale(filepath) and os.path.exists(filepath):
        print(f"Using cached tournament details for Tournament ID: {tournament_id}...")
        with open(filepath, 'r') as f:
            return json.load(f)

    print(f"Fetching full tournament details for Tournament ID: {tournament_id}...")
    url = f"{BASE_URL}/tournaments/{tournament_id}"
    params = {'includeArenas': 'true'}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        tournament_details = response.json()
        with open(filepath, 'w') as f:
            json.dump(tournament_details, f, indent=4)
        print(f"Saved full tournament details for tournament {tournament_id}")
        return tournament_details
    except requests.exceptions.RequestException as e:
        print(f"Error fetching full tournament details for tournament {tournament_id}: {e}")
        return None

def fetch_data(excluded_series_names, finals_mapping, parse_series_name_func):
    print("Fetching data from Matchplay API...")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    series_list = get_series_by_owner(USER_ID)
    
    for series in series_list:
        if series['name'] in excluded_series_names:
            continue

        series_id = series['seriesId']
        series_filepath = os.path.join(DATA_DIR, f"series_{series_id}.json")

        if not is_cache_stale(series_filepath) and os.path.exists(series_filepath):
            with open(series_filepath, 'r') as f:
                series_data_raw = json.load(f)
        else:
            print(f"Fetching details for Series ID: {series_id}...")
            url = f"{BASE_URL}/series/{series_id}"
            params = {'includeDetails': 'true'}
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            series_data_raw = response.json()
            with open(series_filepath, 'w') as f:
                json.dump(series_data_raw, f, indent=4)

        # Process main season tournaments
        if 'data' in series_data_raw and 'tournamentIds' in series_data_raw['data']:
            for tournament_id in series_data_raw['data']['tournamentIds']:
                fetch_tournament_games(tournament_id, series_status=series['status'])

        # Process finals tournaments
        year, season_name_parsed, league_name_parsed = parse_series_name_func(series['name'])
        if league_name_parsed in finals_mapping and year != "N/A" and season_name_parsed != "N/A":
            key = f"{season_name_parsed} {year}"
            finals_tournament_ids = finals_mapping[league_name_parsed].get(key)
            if finals_tournament_ids:
                fetch_finals_results(finals_tournament_ids, series_status=series['status'])
                t_ids = finals_tournament_ids if isinstance(finals_tournament_ids, list) else [finals_tournament_ids]
                for tid in t_ids:
                    fetch_tournament_games(tid, series_status=series['status'])
