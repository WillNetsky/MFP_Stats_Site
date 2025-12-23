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
    Identifies instances where a player won the first 4 games of a league night and then did not win the last one.
    """
    almost_perfect_nights = []

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        year, season_name, league_name = parse_series_name(series_name)
        league_type = 'Combined'
        if league_name == "MFPinball":
            league_type = 'MFP'
        elif league_name == "MFLadies Pinball":
            league_type = 'MFLP'
        
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        for tournament_id_str, games_list in series_data_raw.get('tournament_games_data', {}).items():
            tournament_id = int(tournament_id_str)
            
            # Group games by player
            player_games = defaultdict(list)
            for game in games_list:
                if 'playerIds' in game:
                    for pid in game['playerIds']:
                        player_games[pid].append(game)
            
            for player_id, p_games in player_games.items():
                if len(p_games) == 5:
                    # Sort by roundId, then startedAt, then gameId
                    p_games.sort(key=lambda x: (x.get('roundId', 0), x.get('startedAt', ''), x.get('gameId', 0)))
                    
                    won_first_4 = True
                    for i in range(4):
                        game = p_games[i]
                        if not ('resultPositions' in game and game['resultPositions'] and game['resultPositions'][0] == player_id):
                            won_first_4 = False
                            break
                    
                    if won_first_4:
                        # Check if lost 5th
                        last_game = p_games[4]
                        if 'resultPositions' in last_game and last_game['resultPositions'] and last_game['resultPositions'][0] != player_id:
                            almost_perfect_nights.append({
                                'playerId': player_id,
                                'name': player_name_map.get(player_id, 'Unknown Player'),
                                'seriesId': series_id,
                                'seriesName': series_name,
                                'tournamentId': tournament_id,
                                'week_num': tournament_id_to_week_num.get(tournament_id, 'N/A'),
                                'wins': 4,
                                'total_games': 5,
                                'league_type': league_type
                            })
    return almost_perfect_nights
