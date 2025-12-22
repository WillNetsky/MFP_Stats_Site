import os
import json
import re
from collections import defaultdict

from config import DATA_DIR
from api_client import fetch_tournament_games

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
                
                if series_data_raw['data']['name'] in excluded_series_names:
                    print(f"Skipping excluded series during load: {series_data_raw['data']['name']} (ID: {series_data_raw['data']['seriesId']})")
                    continue
                
                series_id = series_data_raw['data']['seriesId']
                series_status = series_data_raw['data']['status']

                series_data_raw['tournament_games_data'] = {}
                if 'tournamentIds' in series_data_raw['data']:
                    for tournament_id in series_data_raw['data']['tournamentIds']:
                        games = fetch_tournament_games(tournament_id, series_status=series_status)
                        if games and games.get('data'):
                            series_data_raw['tournament_games_data'][tournament_id] = games['data']
                
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
    
    original_name = series_name

    year_match = re.search(r'(\d{4})', series_name)
    if year_match:
        year = year_match.group(1)
        series_name_without_year = series_name.replace(year, '').strip()
    else:
        series_name_without_year = series_name

    if "MFPinball" in original_name or "MFP" in original_name:
        league_name = "MFPinball"
    elif "Monterey Flipper Ladies Pinball" in original_name or "MFLadies" in original_name:
        league_name = "MFLadies Pinball"
    
    season_keywords = ["Fall", "Summer", "Winter", "Spring"]
    for keyword in season_keywords:
        if keyword in series_name_without_year:
            season_name = keyword
            break
    
    if season_name == "N/A":
        if "League" in series_name_without_year:
            season_name = "League"
        elif "Season" in series_name_without_year:
            season_name = "Season"

    return year, season_name, league_name

def apply_year_corrections_to_seasons_list(seasons_list):
    """Applies specific year correction logic to a list of season entries."""
    seasons_list.sort(key=lambda x: x['seriesId'])
    
    mflp_2018_assigned = 0
    for season in seasons_list:
        if season['seriesId'] == 5198 and season['league_name'] == "MFPinball":
            season['year'] = "2026"
            continue

        if season['year'] == "N/A":
            if season['league_name'] == "MFLadies Pinball":
                if mflp_2018_assigned < 2:
                    season['year'] = "2018"
                    mflp_2018_assigned += 1
                else:
                    season['year'] = "2024"
            elif season['league_name'] == "MFPinball":
                season['year'] = "2024"
            else:
                season['year'] = "2024"
    
    seasons_list.sort(key=lambda x: x['seriesId'], reverse=True)
    return seasons_list

def process_game_data(series_data):
    """
    Processes raw game data for a series to extract detailed player performance.
    """
    by_machine = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    by_player = defaultdict(lambda: defaultdict(int))

    for tournament_id, games_list in series_data.get('tournament_games_data', {}).items():
        for game in games_list:
            arena_name = game.get('arena', {}).get('name', 'Unknown Arena')
            num_players = len(game['playerIds'])

            for player_id in game['playerIds']:
                try:
                    position = game['resultPositions'].index(player_id) + 1
                except (ValueError, TypeError):
                    continue 

                by_player[player_id]['total_games'] += 1
                
                if position == 1:
                    by_player[player_id]['1st'] += 1
                elif position == 2:
                    if num_players == 4:
                        by_player[player_id]['2nd_4p'] += 1
                    elif num_players == 3:
                        by_player[player_id]['2nd_3p'] += 1
                elif position == 3:
                    if num_players == 4:
                        by_player[player_id]['3rd_4p'] += 1
                    elif num_players == 3:
                        by_player[player_id]['4th_combined'] += 1
                elif position == 4:
                    if num_players == 4:
                        by_player[player_id]['4th_combined'] += 1

                by_machine[player_id][arena_name]['total_plays'] += 1
                if position == 1:
                    by_machine[player_id][arena_name]['1st_place'] += 1
                elif position == 2:
                    by_machine[player_id][arena_name]['2nd_place'] += 1
                elif position == 3:
                    by_machine[player_id][arena_name]['3rd_place'] += 1

    return {'by_machine': by_machine, 'by_player': by_player}

def find_almost_perfect_nights(all_series_data):
    """
    Identifies instances where a player won 4 out of 5 games in a single weekly tournament.
    """
    almost_perfect_nights = []

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        for tournament_id_str, games_list in series_data_raw.get('tournament_games_data', {}).items():
            tournament_id = int(tournament_id_str)
            
            if len(games_list) == 5:
                player_wins_in_tournament = defaultdict(int)
                
                for game in games_list:
                    if 'resultPositions' in game and 'playerIds' in game and game['resultPositions']:
                        winner_id = game['resultPositions'][0]
                        player_wins_in_tournament[winner_id] += 1
                
                for player_id, win_count in player_wins_in_tournament.items():
                    if win_count == 4:
                        almost_perfect_nights.append({
                            'playerId': player_id,
                            'name': player_name_map.get(player_id, 'Unknown Player'),
                            'seriesId': series_id,
                            'seriesName': series_name,
                            'tournamentId': tournament_id,
                            'week_num': tournament_id_to_week_num.get(tournament_id, 'N/A'),
                            'wins': win_count,
                            'total_games': 5
                        })
    return almost_perfect_nights
