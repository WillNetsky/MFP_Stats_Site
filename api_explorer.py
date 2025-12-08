import os
import requests
import pprint
from dotenv import load_dotenv

load_dotenv()

# Matchplay API configuration
API_KEY = os.getenv("MATCHPLAY_API_KEY")
USER_ID = os.getenv("USER_ID") # Not directly used in this version, but kept for consistency
BASE_URL = "https://app.matchplay.events/api"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def get_series_details(series_id):
    """Fetches detailed information for a single series."""
    print(f"\\n--- Fetching details for Series ID: {series_id} ---")
    url = f"{BASE_URL}/series/{series_id}"
    params = {'includeDetails': 'true'}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        series_data = response.json()
        pprint.pprint(series_data)
        return series_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching series details: {e}")
        return None

def get_tournaments_for_series(series_id):
    """Fetches all tournaments associated with a given series."""
    print(f"\\n--- Fetching Tournaments for Series ID: {series_id} ---")
    url = f"{BASE_URL}/tournaments"
    params = {'series': series_id}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        tournaments_data = response.json()
        pprint.pprint(tournaments_data)
        return tournaments_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tournaments for series: {e}")
        return None

def get_tournament_details(tournament_id):
    """Fetches detailed information for a single tournament."""
    print(f"\\n--- Fetching details for Tournament ID: {tournament_id} ---")
    url = f"{BASE_URL}/tournaments/{tournament_id}"
    # Include players and playoffs info to see if it links to finals
    params = {'includePlayers': 'true', 'includePlayoffs': 'true'} 
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        tournament_data = response.json()
        pprint.pprint(tournament_data)
        return tournament_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tournament details: {e}")
        return None

if __name__ == "__main__":
    if not API_KEY:
        print("Please create a .env file and add your MATCHPLAY_API_KEY.")
    else:
        # --- EXPLORATION STEPS ---
        # 1. Replace with a series ID you want to investigate (e.g., one you know has finals)
        EXPLORE_SERIES_ID = 3822 # Example Series ID from previous output

        # Get series details
        series_data = get_series_details(EXPLORE_SERIES_ID)

        # Get all tournaments for that series
        tournaments_in_series = get_tournaments_for_series(EXPLORE_SERIES_ID)

        # If there are tournaments, let's look at the details of one or more
        if tournaments_in_series and tournaments_in_series.get('data'):
            print("\\n--- Exploring individual tournament details for potential finals links ---")
            # Let's check the last tournament in the list, as finals are often the last event
            last_tournament_id = tournaments_in_series['data'][-1]['tournamentId']
            get_tournament_details(last_tournament_id)

            # You can uncomment and change the index to explore other tournaments
            # get_tournament_details(tournaments_in_series['data'][0]['tournamentId'])
            
            # If you find a 'linkedTournamentId' in the output above,
            # you can then fetch its details:
            # get_tournament_details(LINKED_TOURNAMENT_ID_HERE)
