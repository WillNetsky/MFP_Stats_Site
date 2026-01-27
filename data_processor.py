import os
import json
import re
from collections import defaultdict
from datetime import datetime

from config import DATA_DIR, MFLADIES_LEAGUE_NAMES
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
    elif any(name in original_name for name in MFLADIES_LEAGUE_NAMES):
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

def extract_year_from_series_data(series_data_raw):
    """
    Attempts to extract the year from the series data (games start date).
    Returns the year as a string if found, otherwise None.
    """
    tournament_games_data = series_data_raw.get('tournament_games_data', {})
    if tournament_games_data:
        # Get the first tournament's games
        first_tournament_games = next(iter(tournament_games_data.values()), [])
        if first_tournament_games:
            # Get the first game's start date
            first_game = first_tournament_games[0]
            started_at = first_game.get('startedAt')
            if started_at:
                try:
                    return str(datetime.strptime(started_at.split('T')[0], "%Y-%m-%d").year)
                except ValueError:
                    pass
    return None

def apply_year_corrections_to_seasons_list(seasons_list):
    """Applies specific year correction logic to a list of season entries."""
    seasons_list.sort(key=lambda x: x['seriesId'])
    
    mflp_2018_assigned = 0
    for season in seasons_list:
        # Check if we can get the year from the games data
        series_data_raw = season.get('original_series_data')
        if series_data_raw:
            data_year = extract_year_from_series_data(series_data_raw)
            if data_year:
                season['year'] = data_year
                continue # Skip other corrections if we found a valid year

        if season['seriesId'] == 5198 and season['league_name'] == "MFPinball":
            season['year'] = "2026"
            continue
        
        if season['seriesId'] == 5199 and season['league_name'] == "MFLadies Pinball":
            season['year'] = "2026"
            continue
        
        # Correction for MFPinball Winter 2017 (actually 2018)
        if season['seriesName'] == "MFPinball Winter 2017" and season['year'] == "2017":
             season['year'] = "2018"

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

            for p_idx, player_id in enumerate(game['playerIds']):
                try:
                    position = game['resultPositions'].index(player_id) + 1
                except (ValueError, TypeError):
                    continue 

                by_player[player_id]['total_games'] += 1
                by_player[player_id][f'order_{p_idx + 1}'] += 1

                by_machine[player_id][arena_name]['total_plays'] += 1
                
                if position == 1:
                    by_player[player_id]['1st'] += 1
                    by_machine[player_id][arena_name]['1st'] += 1
                elif position == 2:
                    if num_players == 4:
                        by_player[player_id]['2nd_4p'] += 1
                        by_machine[player_id][arena_name]['2nd_4p'] += 1
                    elif num_players == 3:
                        by_player[player_id]['2nd_3p'] += 1
                        by_machine[player_id][arena_name]['2nd_3p'] += 1
                elif position == 3:
                    if num_players == 4:
                        by_player[player_id]['3rd_4p'] += 1
                        by_machine[player_id][arena_name]['3rd_4p'] += 1
                    elif num_players == 3:
                        by_player[player_id]['4th_combined'] += 1
                        by_machine[player_id][arena_name]['4th_combined'] += 1
                elif position == 4:
                    if num_players == 4:
                        by_player[player_id]['4th_combined'] += 1
                        by_machine[player_id][arena_name]['4th_combined'] += 1

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
        
        data_year = extract_year_from_series_data(series_data_raw)
        if data_year:
            year = data_year

        league_type = 'Combined'
        if league_name == "MFPinball":
            league_type = 'MFP'
        elif league_name == "MFLadies Pinball":
            league_type = 'MFLP'
        
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        for tournament_id_str, games_list in series_data_raw.get('tournament_games_data', {}).items():
            tournament_id = int(tournament_id_str)
            week_num = tournament_id_to_week_num.get(tournament_id, 'N/A')
            
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
                                'year': year,
                                'season_name': season_name,
                                'week_num': week_num,
                                'league_type': league_type
                            })
    return almost_perfect_nights

def find_wooden_nickels(all_series_data):
    """
    Identifies instances where a player played 5 games in a league night and got last place in all of them (5 points total).
    """
    wooden_nickels = []

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        year, season_name, league_name = parse_series_name(series_name)
        
        data_year = extract_year_from_series_data(series_data_raw)
        if data_year:
            year = data_year

        league_type = 'Combined'
        if league_name == "MFPinball":
            league_type = 'MFP'
        elif league_name == "MFLadies Pinball":
            league_type = 'MFLP'
        
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        for tournament_id_str, games_list in series_data_raw.get('tournament_games_data', {}).items():
            tournament_id = int(tournament_id_str)
            week_num = tournament_id_to_week_num.get(tournament_id)
            if week_num is None:
                continue

            # Group games by player
            player_games = defaultdict(list)
            for game in games_list:
                if 'playerIds' in game:
                    for pid in game['playerIds']:
                        player_games[pid].append(game)
            
            for player_id, p_games in player_games.items():
                if len(p_games) == 5:
                    all_last_place = True
                    for game in p_games:
                        # Check if player is last in resultPositions
                        if 'resultPositions' in game and game['resultPositions']:
                            if game['resultPositions'][-1] != player_id:
                                all_last_place = False
                                break
                        else:
                            all_last_place = False
                            break
                    
                    if all_last_place:
                        player_name = player_name_map.get(player_id, 'Unknown Player')
                        wooden_nickels.append({
                            'playerId': player_id,
                            'name': player_name,
                            'seriesId': series_id,
                            'seriesName': series_name,
                            'year': year,
                            'season_name': season_name,
                            'week_num': week_num,
                            'league_type': league_type
                        })
    return wooden_nickels

def find_biggest_drops(all_series_data):
    """
    Identifies the biggest week-to-week point drops for players within a season.
    """
    biggest_drops = []

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        year, season_name, league_name = parse_series_name(series_name)
        
        data_year = extract_year_from_series_data(series_data_raw)
        if data_year:
            year = data_year

        league_type = 'Combined'
        if league_name == "MFPinball":
            league_type = 'MFP'
        elif league_name == "MFLadies Pinball":
            league_type = 'MFLP'
        
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        if 'tournamentPoints' in series and series['tournamentPoints']:
            # Organize points by player and week
            player_weekly_points = defaultdict(list)
            
            for tournament_id_str, player_points_map_val in series['tournamentPoints'].items():
                current_tournament_id = int(tournament_id_str)
                week_num = tournament_id_to_week_num.get(current_tournament_id)
                if week_num is None:
                    continue

                if isinstance(player_points_map_val, dict):
                    for player_id_str, points_str in player_points_map_val.items():
                        points = float(points_str)
                        player_id = int(player_id_str)
                        player_weekly_points[player_id].append({'week': week_num, 'points': points})

            # Calculate drops
            for player_id, weeks_data in player_weekly_points.items():
                # Sort by week number
                weeks_data.sort(key=lambda x: x['week'])
                
                for i in range(len(weeks_data) - 1):
                    week1 = weeks_data[i]
                    week2 = weeks_data[i+1]
                    
                    # Check if weeks are consecutive
                    if week2['week'] == week1['week'] + 1:
                        drop = week1['points'] - week2['points']
                        if drop > 0:
                            player_name = player_name_map.get(player_id, 'Unknown Player')
                            biggest_drops.append({
                                'playerId': player_id,
                                'name': player_name,
                                'seriesId': series_id,
                                'seriesName': series_name,
                                'year': year,
                                'season_name': season_name,
                                'week_from': week1['week'],
                                'points_from': week1['points'],
                                'week_to': week2['week'],
                                'points_to': week2['points'],
                                'drop': drop,
                                'league_type': league_type
                            })
    
    # Sort by drop amount descending
    biggest_drops.sort(key=lambda x: x['drop'], reverse=True)
    return biggest_drops

def _load_tournament_local_date(tournament_id):
    """Loads the local start date from a tournament details file."""
    detail_path = os.path.join(DATA_DIR, f"tournament_details_{tournament_id}.json")
    if os.path.exists(detail_path):
        with open(detail_path, 'r') as f:
            detail = json.load(f)
        start_local = detail.get('data', {}).get('startLocal')
        if start_local:
            try:
                return datetime.strptime(start_local.split(' ')[0], "%Y-%m-%d")
            except ValueError:
                pass
    return None

def find_tournaments_on_this_day(all_series_data):
    """
    Finds tournaments that happened on the current day (month and day) in any year.
    Uses tournament detail startLocal to get the correct local date rather than
    the game startedAt UTC timestamp (which can be off by a day).
    """
    today = datetime.now()
    today_month = today.month
    today_day = today.day

    tournaments_on_this_day = []

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']

        year, season_name, league_name = parse_series_name(series_name)
        data_year = extract_year_from_series_data(series_data_raw)
        if data_year:
            year = data_year

        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        for tournament_id in series.get('tournamentIds', []):
            week_num = tournament_id_to_week_num.get(tournament_id, 'N/A')

            # Use local start date from tournament details
            tournament_date = _load_tournament_local_date(tournament_id)
            if not tournament_date:
                continue

            if tournament_date.month == today_month and tournament_date.day == today_day:
                # Find the winner of the tournament
                winner_name = "Unknown"
                winner_id = None
                if 'tournamentPoints' in series and str(tournament_id) in series['tournamentPoints']:
                    player_points_map = series['tournamentPoints'][str(tournament_id)]
                    if player_points_map:
                        winner_id_str = max(player_points_map, key=lambda p_id: float(player_points_map[p_id]))
                        winner_id = int(winner_id_str)
                        winner_name = player_name_map.get(winner_id, "Unknown")

                tournaments_on_this_day.append({
                    'date': tournament_date.strftime("%Y-%m-%d"),
                    'year': tournament_date.year,
                    'seriesId': series_id,
                    'seriesName': series_name,
                    'week_num': week_num,
                    'winner_name': winner_name,
                    'winner_id': winner_id
                })

    # Sort by year descending
    tournaments_on_this_day.sort(key=lambda x: x['year'], reverse=True)
    return tournaments_on_this_day

def find_one_hit_wonders(all_series_data):
    """
    Identifies players who have only played in exactly one league night across all series.
    """
    player_appearances = defaultdict(list)
    player_name_map = {}

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        year, season_name, league_name = parse_series_name(series_name)
        data_year = extract_year_from_series_data(series_data_raw)
        if data_year:
            year = data_year
            
        league_type = 'Combined'
        if league_name == "MFPinball":
            league_type = 'MFP'
        elif league_name == "MFLadies Pinball":
            league_type = 'MFLP'

        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series.get('tournamentIds', []))}
        
        # Update player name map
        for p in series.get('players', []):
            player_name_map[p['playerId']] = p['name']

        if 'tournamentPoints' in series and series['tournamentPoints']:
            for tournament_id_str, player_points_map_val in series['tournamentPoints'].items():
                current_tournament_id = int(tournament_id_str)
                week_num = tournament_id_to_week_num.get(current_tournament_id)
                if week_num is None:
                    continue

                # Get date for this tournament: prefer local date from details, fall back to game data
                tournament_date = "Unknown Date"
                local_date = _load_tournament_local_date(current_tournament_id)
                if local_date:
                    tournament_date = local_date.strftime("%Y-%m-%d")
                elif 'tournament_games_data' in series_data_raw and current_tournament_id in series_data_raw['tournament_games_data']:
                    games = series_data_raw['tournament_games_data'][current_tournament_id]
                    if games:
                        first_game = games[0]
                        started_at = first_game.get('startedAt')
                        if started_at:
                            try:
                                tournament_date = datetime.strptime(started_at.split('T')[0], "%Y-%m-%d").strftime("%Y-%m-%d")
                            except ValueError:
                                pass

                if isinstance(player_points_map_val, dict):
                    for player_id_str, points_str in player_points_map_val.items():
                        points = float(points_str)
                        player_id = int(player_id_str)
                        
                        player_appearances[player_id].append({
                            'date': tournament_date,
                            'seriesId': series_id,
                            'seriesName': series_name,
                            'week_num': week_num,
                            'points': points,
                            'league_type': league_type
                        })

    one_hit_wonders = []
    for player_id, appearances in player_appearances.items():
        if len(appearances) == 1:
            appearance = appearances[0]
            one_hit_wonders.append({
                'playerId': player_id,
                'name': player_name_map.get(player_id, 'Unknown Player'),
                'date': appearance['date'],
                'seriesId': appearance['seriesId'],
                'seriesName': appearance['seriesName'],
                'week_num': appearance['week_num'],
                'points': appearance['points'],
                'league_type': appearance['league_type']
            })
    
    # Sort by date descending
    one_hit_wonders.sort(key=lambda x: x['date'], reverse=True)
    return one_hit_wonders
