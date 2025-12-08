import os
from jinja2 import Environment, FileSystemLoader

from data_processor import load_all_series_data, load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list
from api_client import fetch_finals_results
from config import OUTPUT_DIR, TEMPLATES_DIR, MIN_WEEKS_FOR_IMPROVEMENT

# --- Jinja2 Custom Filters ---
def score_color_filter(score):
    """
    Jinja2 filter to color-code scores based on value.
    5 (worst) -> Red, 20 -> White, 34 -> Green, 35 -> Gold.
    'N/A' or None -> Blank.
    """
    if score is None or score == 'N/A' or score == '-':
        return "" # Blank out if no score

    try:
        score_val = float(score)
    except ValueError:
        return str(score) # Return as is if not a number

    color = ""
    if score_val == 35:
        color = "gold"
    elif score_val <= 5: # Treat 5 and below as pure red
        color = "rgb(255,0,0)"
    elif score_val >= 34: # Treat 34 and above (but not 35) as pure green
        color = "rgb(0,128,0)"
    elif 5 < score_val < 20:
        # Interpolate from Red (255,0,0) at 5 to White (255,255,255) at 20
        t = (score_val - 5) / 15.0 # Scale to 0-1 over the range 5-20
        r = 255
        g = int(255 * t)
        b = int(255 * t)
        color = f"rgb({r},{g},{b})"
    elif 20 <= score_val < 34:
        # Interpolate from White (255,255,255) at 20 to Green (0,128,0) at 34
        t = (score_val - 20) / 14.0 # Scale to 0-1 over the range 20-34
        r = int(255 * (1 - t))
        g = int(255 * (1 - t) + 128 * t)
        b = int(255 * (1 - t))
        color = f"rgb({r},{g},{b})"
    
    # Return a span with inline style for background color
    return f'<span style="background-color: {color}; padding: 2px 5px; border-radius: 3px; display: inline-block; min-width: 25px; text-align: center;">{int(score_val) if score_val == int(score_val) else score_val}</span>'

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

def generate_seasons_page(env, all_series_data):
    """Generates the seasons.html page, separated by league type."""
    print("Generating seasons.html...")
    template = env.get_template('seasons.html')

    mfp_seasons_raw = []
    mflp_seasons_raw = []
    finals_mapping = load_finals_mapping()
    all_years = set()

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        year, season_name_parsed, league_name_parsed = parse_series_name(series_name)
        all_years.add(year)

        season_entry = {
            'seriesId': series_id,
            'seriesName': series_name,
            'year': year, # This might be "N/A" initially
            'season_name': season_name_parsed,
            'league_name': league_name_parsed,
            'status': series['status'],
            'has_finals': "No", # Will be determined after year correction
            'first_place_player': None,
            'second_place_player': None,
            'third_place_player': None,
            'fourth_place_player': None
        }

        if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
            mfp_seasons_raw.append(season_entry)
        elif "MFLadies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
            mflp_seasons_raw.append(season_entry)
    
    # Apply year corrections to the collected lists
    mfp_seasons = apply_year_corrections_to_seasons_list(mfp_seasons_raw)
    mflp_seasons = apply_year_corrections_to_seasons_list(mflp_seasons_raw)

    # Now, with corrected years, determine finals status and top 4 players
    for season in mfp_seasons + mflp_seasons: # Iterate through all seasons
        league_name = season['league_name']
        year = season['year']
        season_name = season['season_name']
        series_id = season['seriesId']
        all_years.add(year)

        # Determine finals status
        finals_tournament_ids = None
        if league_name in finals_mapping and year != "N/A" and season_name != "N/A":
            key = f"{season_name} {year}"
            finals_tournament_ids = finals_mapping[league_name].get(key)
        
        season['has_finals'] = "Yes" if finals_tournament_ids else "No"
        
        # Extract top 4 players from the original series data
        original_series_data_for_top4 = next((s for s in all_series_data if s['data']['seriesId'] == series_id), None)
        if original_series_data_for_top4:
            series_details = original_series_data_for_top4['data']
            player_map = {p['playerId']: p['name'] for p in series_details['players']}
            
            top_players_standings = []
            if season['has_finals'] == "Yes" and finals_tournament_ids:
                finals_standings = fetch_finals_results(finals_tournament_ids)
                if finals_standings:
                    for result in finals_standings:
                        top_players_standings.append({
                            'playerId': result['playerId'],
                            'name': player_map.get(result['playerId'], 'Unknown Player'),
                            'position': result['position']
                        })
                    top_players_standings.sort(key=lambda x: x['position']) # Ensure sorted by position
                else:
                    # Fallback to qualifying standings if finals data is empty
                    print(f"WARNING: Finals data for Season: {season['seriesName']} (ID: {series_id}) is empty. Falling back to qualifying standings.")
                    standings_with_avg = []
                    for standing in series_details['standings']:
                        player_id = standing['playerId']
                        total_raw_points = 0
                        weeks_played = 0
                        if 'tournamentPoints' in series_details:
                            for tournament_id_str, player_points_map in series_details['tournamentPoints'].items():
                                if str(player_id) in player_points_map:
                                    total_raw_points += float(player_points_map[str(player_id)])
                                    weeks_played += 1
                        
                        avg_score = total_raw_points / weeks_played if weeks_played > 0 else 0
                        standings_with_avg.append({**standing, 'avg_score': avg_score})

                    top_players_standings = sorted(standings_with_avg, key=lambda x: (x['position'], -x['avg_score']))
            else:
                # Use qualifying standings with tie-breaking for seasons without finals
                standings_with_avg = []
                for standing in series_details['standings']:
                    player_id = standing['playerId']
                    total_raw_points = 0
                    weeks_played = 0
                    if 'tournamentPoints' in series_details:
                        for tournament_id_str, player_points_map in series_details['tournamentPoints'].items():
                            if str(player_id) in player_points_map:
                                total_raw_points += float(player_points_map[str(player_id)])
                                weeks_played += 1
                    
                    avg_score = total_raw_points / weeks_played if weeks_played > 0 else 0
                    standings_with_avg.append({**standing, 'avg_score': avg_score})

                top_players_standings = sorted(standings_with_avg, key=lambda x: (x['position'], -x['avg_score']))

            # Assign top 4 players to season_entry
            for i, player_data in enumerate(top_players_standings[:4]):
                player_id = player_data['playerId']
                player_name = player_map.get(player_id, 'Unknown Player')
                if i == 0:
                    season['first_place_player'] = {'playerId': player_id, 'name': player_name}
                elif i == 1:
                    season['second_place_player'] = {'playerId': player_id, 'name': player_name}
                elif i == 2:
                        season['third_place_player'] = {'playerId': player_id, 'name': player_name}
                elif i == 3:
                    season['fourth_place_player'] = {'playerId': player_id, 'name': player_name}


    # Re-sort for display (newest first) - already done in apply_year_corrections_to_seasons_list
    # but ensure final sort order is correct if apply_year_corrections_to_seasons_list changes it
    mfp_seasons.sort(key=lambda x: x['seriesId'], reverse=True)
    mflp_seasons.sort(key=lambda x: x['seriesId'], reverse=True)

    sorted_years = sorted([y for y in all_years if y != "N/A"], reverse=True)


    with open(os.path.join(OUTPUT_DIR, 'seasons.html'), 'w') as f:
        f.write(template.render(
            mfp_seasons=mfp_seasons,
            mflp_seasons=mflp_seasons,
            years=sorted_years
        ))
    print("Generated seasons.html")

def generate_season_pages(env, all_series_data):
    """Generates individual season pages."""
    template = env.get_template('season.html')
    finals_mapping = load_finals_mapping()
    
    # First, process all seasons to apply year corrections
    processed_seasons_for_pages = []
    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        
        year, season_name_parsed, league_name_parsed = parse_series_name(series_name)
        processed_seasons_for_pages.append({
            'seriesId': series_id,
            'seriesName': series_name,
            'year': year,
            'season_name': season_name_parsed,
            'league_name': league_name_parsed,
            'original_series_data': series_data_raw # Keep original data for later processing
        })
    
    # Apply year corrections to the entire list of processed seasons
    processed_seasons_for_pages = apply_year_corrections_to_seasons_list(processed_seasons_for_pages)
    
    # Now iterate through the processed seasons to generate individual pages
    for season_entry in processed_seasons_for_pages:
        series_id = season_entry['seriesId']
        series_name = season_entry['seriesName']
        year = season_entry['year']
        season_name_parsed = season_entry['season_name']
        league_name_parsed = season_entry['league_name']
        series = season_entry['original_series_data']['data'] # Get back original series data

        # Determine if season has finals by checking the manual mapping
        finals_tournament_ids = None
        if league_name_parsed in finals_mapping and year != "N/A" and season_name_parsed != "N/A":
            key = f"{season_name_parsed} {year}"
            finals_tournament_ids = finals_mapping[league_name_parsed].get(key)
        
        has_finals = "Yes" if finals_tournament_ids else "No"
        
        # Load finals results if available
        finals_results = None
        if finals_tournament_ids:
            raw_finals_standings = fetch_finals_results(finals_tournament_ids)
            if raw_finals_standings:
                # Create a mapping from playerId to name for easy lookup within this season's players
                player_name_map_for_finals = {p['playerId']: p['name'] for p in series['players']}
                finals_results = []
                for result in raw_finals_standings:
                    finals_results.append({
                        'position': result['position'],
                        'playerId': result['playerId'],
                        'name': player_name_map_for_finals.get(result['playerId'], 'Unknown Player')
                    })
                finals_results.sort(key=lambda x: x['position']) # Sort finals results by position

        # Create a mapping from playerId to name for easy lookup
        player_map = {p['playerId']: p['name'] for p in series['players']}
        
        # Create a mapping from tournamentId to week number
        # Assuming tournamentIds are ordered by week
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series['tournamentIds'])}
        
        # Prepare data for the season standings table
        season_players_data = []
        
        # Create a dictionary for finals player positions for quick lookup
        finals_player_positions = {}
        if finals_results:
            for result in finals_results:
                finals_player_positions[result['playerId']] = result['position']

        # Iterate through all players in the series to ensure everyone is included
        for player_info in series['players']:
            player_id = player_info['playerId']
            player_name = player_info['name']

            # Get standing data for the current player in this season (qualifying position)
            player_standing = next((s for s in series['standings'] if s['playerId'] == player_id), None)
            
            qualifying_position = player_standing['position'] if player_standing else 'N/A'
            total_adjusted_points = player_standing['pointsAdjusted'] if player_standing else 0.0
            
            # Determine overall final position
            overall_final_position = 'N/A'
            if player_id in finals_player_positions:
                overall_final_position = finals_player_positions[player_id]
            elif qualifying_position != 'N/A':
                # For players who didn't make finals, their final position is their qualifying position
                overall_final_position = qualifying_position

            weekly_scores_raw = []
            total_raw_points = 0.0
            
            # Collect weekly scores
            if 'tournamentPoints' in series and series['tournamentPoints']:
                for tournament_id_str in series['tournamentPoints']:
                    # Ensure we get points for this specific player
                    if str(player_id) in series['tournamentPoints'][tournament_id_str]:
                        points = float(series['tournamentPoints'][tournament_id_str][str(player_id)])
                        weekly_scores_raw.append({'tournament_id': int(tournament_id_str), 'points': points})
                        total_raw_points += points
            
            # Sort weekly scores by tournament_id to get them in week order
            weekly_scores_raw.sort(key=lambda x: x['tournament_id'])

            # Create a list of 10 weekly scores, filling with 0 or 'N/A' for missing weeks
            # Assuming a maximum of 10 weeks per season
            weekly_scores_ordered = ['N/A'] * 10 
            num_weeks_played_by_player = 0
            for score_entry in weekly_scores_raw:
                week_num = tournament_id_to_week_num.get(score_entry['tournament_id'])
                if week_num is not None and 1 <= week_num <= 10:
                    weekly_scores_ordered[week_num - 1] = score_entry['points']
                    num_weeks_played_by_player += 1
            
            average_points_per_week = total_raw_points / num_weeks_played_by_player if num_weeks_played_by_player > 0 else 0.0

            season_players_data.append({
                'playerId': player_id,
                'name': player_name,
                'qualifying_position': qualifying_position, # Keep qualifying position separate
                'overall_final_position': overall_final_position, # New overall final position
                'total_adjusted_points': total_adjusted_points,
                'total_raw_points': round(total_raw_points, 2),
                'average_points_per_week': round(average_points_per_week, 2),
                'weekly_scores': weekly_scores_ordered # This will be a list of 10 scores
            })
        
        # Sort season_players_data by overall_final_position
        season_players_data.sort(key=lambda x: x['overall_final_position'] if isinstance(x['overall_final_position'], int) else float('inf'))

        with open(os.path.join(OUTPUT_DIR, f"season_{series_id}.html"), 'w') as f:
            f.write(template.render(
                season=series,
                season_players_data=season_players_data, # Pass the new structured data
                players=series['players'], # Keep for other uses if needed
                has_finals=has_finals, # Pass has_finals to the template
                finals_tournament_ids=finals_tournament_ids, # Pass finals_tournament_ids
                finals_results=finals_results # Pass finals results
            ))
        print(f"Generated season_{series_id}.html")

def generate_player_pages(env, all_series_data):
    """Generates individual player pages and a main players list page."""
    unique_players = {}
    player_categorized_seasons = {} # To store aggregated and categorized data for each player
    finals_mapping = load_finals_mapping()

    for series_data_raw in all_series_data:
        series_data = series_data_raw['data']
        series_id = series_data['seriesId']
        series_name = series_data['name']
        
        year, season_name_parsed, league_name_parsed = parse_series_name(series_name)

        # Determine if season has finals
        finals_tournament_ids = None
        if league_name_parsed in finals_mapping and year != "N/A" and season_name_parsed != "N/A":
            key = f"{season_name_parsed} {year}"
            finals_tournament_ids = finals_mapping[league_name_parsed].get(key)
        
        finals_player_positions = {}
        if finals_tournament_ids:
            finals_standings = fetch_finals_results(finals_tournament_ids)
            if finals_standings:
                finals_player_positions = {res['playerId']: res['position'] for res in finals_standings}

        for player_info in series_data['players']:
            player_id = player_info['playerId']
            if player_id not in unique_players:
                unique_players[player_id] = player_info
                player_categorized_seasons[player_id] = {
                    'player_info': player_info,
                    'mfp_seasons': [],
                    'mflp_seasons': []
                }
            
            # Find player's standing in this season
            player_standing = next((s for s in series_data['standings'] if s['playerId'] == player_id), None)
            
            # Determine final position
            final_position = player_standing['position'] if player_standing else 'N/A'
            if player_id in finals_player_positions:
                final_position = finals_player_positions[player_id]

            weekly_performance_raw = []
            total_raw_points = 0.0
            
            if 'tournamentPoints' in series_data:
                for tournament_id_str, player_points_map in series_data['tournamentPoints'].items():
                    if str(player_id) in player_points_map:
                        points = float(player_points_map[str(player_id)])
                        weekly_performance_raw.append({'tournament_id': int(tournament_id_str), 'points': points})
                        total_raw_points += points
            
            # Sort weekly performance from best to worst for display
            weekly_performance_sorted = sorted(weekly_performance_raw, key=lambda x: x['points'], reverse=True)
            
            # Extract top 6 scores
            top_6_scores = [week['points'] for week in weekly_performance_sorted[:6]]
            # Pad with None if less than 6 scores
            top_6_scores.extend([None] * (6 - len(top_6_scores)))

            # Calculate summary statistics for the season
            num_weeks_played = len(weekly_performance_raw)
            average_points_per_week = total_raw_points / num_weeks_played if num_weeks_played > 0 else 0

            season_entry = {
                'seriesId': series_id,
                'seriesName': series_name,
                'year': year,
                'season_name': season_name_parsed,
                'league_name': league_name_parsed,
                'summary_stats': {
                    'final_position': final_position,
                    'total_raw_points': round(total_raw_points, 2),
                    'total_adjusted_points': player_standing['pointsAdjusted'] if player_standing else 0,
                    'weeks_played': num_weeks_played,
                    'average_points_per_week': round(average_points_per_week, 2),
                    'top_6_scores': top_6_scores # List of top 6 scores
                }
            }

            if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
                player_categorized_seasons[player_id]['mfp_seasons'].append(season_entry)
            elif "MFLadies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
                player_categorized_seasons[player_id]['mflp_seasons'].append(season_entry)

    players_list = list(unique_players.values())
    
    # Apply year correction logic to player's seasons
    for player_id, data in player_categorized_seasons.items():
        data['mfp_seasons'] = apply_year_corrections_to_seasons_list(data['mfp_seasons'])
        data['mflp_seasons'] = apply_year_corrections_to_seasons_list(data['mflp_seasons'])

    # Generate individual player pages
    player_template = env.get_template('player.html')
    for player_id, data in player_categorized_seasons.items():
        player = data['player_info']
        
        with open(os.path.join(OUTPUT_DIR, f"player_{player_id}.html"), 'w') as f:
            f.write(player_template.render(
                player=player,
                mfp_seasons=data['mfp_seasons'],
                mflp_seasons=data['mflp_seasons']
            ))
        print(f"Generated player_{player_id}.html")

    # Generate main players list page
    players_list_template = env.get_template('players.html')
    with open(os.path.join(OUTPUT_DIR, 'players.html'), 'w') as f:
        f.write(players_list_template.render(players=players_list))
    print("Generated players.html")
    
    return player_categorized_seasons

def generate_leaderboards_page(env, all_series_data, player_categorized_seasons):
    """Generates the all-time leaderboards page, separated by league type."""
    print("Generating leaderboards.html...")
    
    mfp_players_stats = {}
    mflp_players_stats = {}
    
    # Track all winning scores to determine the global minimum winning score
    all_winning_scores = []
    perfect_nights_leaderboard = [] # New list for perfect nights

    # Create a temporary list of season entries to apply year corrections consistently
    temp_season_entries = []
    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_id = series['seriesId']
        series_name = series['name']
        year, season_name_parsed, league_name_parsed = parse_series_name(series_name)
        temp_season_entries.append({
            'seriesId': series_id,
            'seriesName': series_name,
            'year': year,
            'season_name': season_name_parsed,
            'league_name': league_name_parsed,
            'original_series_data': series_data_raw # Keep original data
        })
    
    # Apply year corrections to this temporary list
    corrected_temp_season_entries = apply_year_corrections_to_seasons_list(temp_season_entries)
    # Re-index for easy lookup by seriesId
    corrected_seasons_map = {s['seriesId']: s for s in corrected_temp_season_entries}


    for series_data_raw in all_series_data:
        series_data = series_data_raw['data']
        series_id = series_data['seriesId']
        series_name = series_data['name']
        
        # Get the corrected year and parsed names from the pre-processed map
        corrected_season_info = corrected_seasons_map.get(series_id, {})
        year = corrected_season_info.get('year', 'N/A')
        season_name_parsed = corrected_season_info.get('season_name', 'N/A')
        league_name_parsed = corrected_season_info.get('league_name', 'Other')

        target_stats_dict = None
        if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
            target_stats_dict = mfp_players_stats
        elif "MFLadies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
            target_stats_dict = mflp_players_stats
        
        # --- Process for All-Time Leaderboards ---
        if target_stats_dict is not None:
            for player_info in series_data['players']:
                player_id = player_info['playerId']
                player_name = player_info['name']
                ifpa_id = player_info.get('ifpaId')

                if player_id not in target_stats_dict:
                    target_stats_dict[player_id] = {
                        'playerId': player_id,
                        'name': player_name,
                        'ifpaId': ifpa_id,
                        'total_adjusted_points': 0.0,
                        'total_raw_points': 0.0, # New field
                        'top_4_finishes': {1: 0, 2: 0, 3: 0, 4: 0},
                        'best_season_score': {'score': 0.0, 'seriesId': None, 'seriesName': None, 'year': None, 'season_name': None, 'final_position': None},
                        'seasons_played_count': 0,
                        'total_weeks_played': 0, # New field
                        'weekly_wins': 0 # New field
                    }
                
                # Update player info (name/ifpaId might be more recent in later series)
                target_stats_dict[player_id]['name'] = player_name
                if ifpa_id: # Only update if not None
                    target_stats_dict[player_id]['ifpaId'] = ifpa_id

                # Get standing data for the current player in this season
                player_standing = next((s for s in series_data['standings'] if s['playerId'] == player_id), None)
                
                # Determine overall final position for this season
                overall_final_position_for_season = 'N/A'
                finals_tournament_ids = None
                if league_name_parsed in load_finals_mapping() and year != "N/A" and season_name_parsed != "N/A":
                    key = f"{season_name_parsed} {year}"
                    finals_tournament_ids = load_finals_mapping()[league_name_parsed].get(key)
                
                if finals_tournament_ids:
                    finals_standings = fetch_finals_results(finals_tournament_ids)
                    if finals_standings:
                        finals_player_positions = {res['playerId']: res['position'] for res in finals_standings}
                        if player_id in finals_player_positions:
                            overall_final_position_for_season = finals_player_positions[player_id]
                        elif player_standing:
                            overall_final_position_for_season = player_standing['position']
                elif player_standing:
                    overall_final_position_for_season = player_standing['position']


                if player_standing:
                    points_adjusted = player_standing['pointsAdjusted']
                    
                    target_stats_dict[player_id]['total_adjusted_points'] += points_adjusted
                    target_stats_dict[player_id]['seasons_played_count'] += 1

                    if isinstance(overall_final_position_for_season, int) and 1 <= overall_final_position_for_season <= 4:
                        target_stats_dict[player_id]['top_4_finishes'][overall_final_position_for_season] += 1
                    
                    if overall_final_position_for_season == 1 and points_adjusted is not None:
                        all_winning_scores.append(points_adjusted)

                    if points_adjusted > target_stats_dict[player_id]['best_season_score']['score']:
                        target_stats_dict[player_id]['best_season_score'] = {
                            'score': points_adjusted,
                            'seriesId': series_id,
                            'seriesName': series_name,
                            'year': year,
                            'season_name': season_name_parsed,
                            'final_position': overall_final_position_for_season # Use overall final position
                        }
        
        # --- Process for Perfect Nights and Total Raw Points ---
        player_map = {p['playerId']: p['name'] for p in series_data['players']}
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series_data['tournamentIds'])}

        if 'tournamentPoints' in series_data and series_data['tournamentPoints']:
            for tournament_id_str, player_points_map_val in series_data['tournamentPoints'].items():
                current_tournament_id = int(tournament_id_str)
                week_num = tournament_id_to_week_num.get(current_tournament_id)
                if week_num is None: # Skip if week number cannot be determined
                    continue

                if isinstance(player_points_map_val, dict): # Ensure it's a dict before calling .items()
                    weekly_winner_id = None
                    max_score = -1
                    for player_id_str, points_str in player_points_map_val.items():
                        points = float(points_str)
                        player_id = int(player_id_str)
                        
                        # Add to total raw points and weeks played
                        if target_stats_dict and player_id in target_stats_dict:
                            target_stats_dict[player_id]['total_raw_points'] += points
                            target_stats_dict[player_id]['total_weeks_played'] += 1

                        if points > max_score:
                            max_score = points
                            weekly_winner_id = player_id

                        if points == 35.0:
                            player_name = player_map.get(player_id, 'Unknown Player')
                            perfect_nights_leaderboard.append({
                                'playerId': player_id,
                                'name': player_name,
                                'seriesId': series_id,
                                'seriesName': series_name,
                                'year': year,
                                'season_name': season_name_parsed,
                                'week_num': week_num
                            })
                    
                    if weekly_winner_id and target_stats_dict and weekly_winner_id in target_stats_dict:
                        target_stats_dict[weekly_winner_id]['weekly_wins'] += 1

    # Sort perfect nights by seriesId then week_num
    perfect_nights_leaderboard.sort(key=lambda x: (x['seriesId'], x['week_num']))

    # Determine global minimum winning score
    min_winning_score = min(all_winning_scores) if all_winning_scores else 0.0

    # --- MFP Leaderboards ---
    mfp_leaderboard_data = list(mfp_players_stats.values())
    mfp_total_points_leaderboard = sorted(mfp_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    
    mfp_weekly_wins_leaderboard = sorted([p for p in mfp_leaderboard_data if p['weekly_wins'] > 0], key=lambda x: x['weekly_wins'], reverse=True)

    mfp_top_4_finishes_leaderboard = [p for p in mfp_leaderboard_data if sum(p['top_4_finishes'].values()) > 0]
    mfp_top_4_finishes_leaderboard.sort(key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    mfp_best_season_score_leaderboard = [p for p in mfp_leaderboard_data if p['best_season_score']['score'] >= min_winning_score and isinstance(p['best_season_score']['final_position'], int) and p['best_season_score']['final_position'] <= 10]
    mfp_best_season_score_leaderboard.sort(key=lambda x: x['best_season_score']['score'], reverse=True)

    # --- MFLadies Pinball Leaderboards ---
    mflp_leaderboard_data = list(mflp_players_stats.values())
    mflp_total_points_leaderboard = sorted(mflp_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    
    mflp_weekly_wins_leaderboard = sorted([p for p in mflp_leaderboard_data if p['weekly_wins'] > 0], key=lambda x: x['weekly_wins'], reverse=True)

    mflp_top_4_finishes_leaderboard = [p for p in mflp_leaderboard_data if sum(p['top_4_finishes'].values()) > 0]
    mflp_top_4_finishes_leaderboard.sort(key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    mflp_best_season_score_leaderboard = [p for p in mflp_leaderboard_data if p['best_season_score']['score'] >= min_winning_score and isinstance(p['best_season_score']['final_position'], int) and p['best_season_score']['final_position'] <= 10]
    mflp_best_season_score_leaderboard.sort(key=lambda x: x['best_season_score']['score'], reverse=True)

    # --- Most Improved Player Leaderboards ---
    mfp_most_improved_leaderboard = []
    mflp_most_improved_leaderboard = []

    for player_id, player_data in player_categorized_seasons.items():
        player_info = player_data['player_info']
        
        # Process MFP seasons for improvement
        mfp_seasons_sorted = sorted(player_data['mfp_seasons'], key=lambda x: x['seriesId'])
        best_mfp_improvement = {'player': player_info, 'improvement_percent': -1, 'season1': None, 'season2': None}
        for i in range(len(mfp_seasons_sorted) - 1):
            season1 = mfp_seasons_sorted[i]
            season2 = mfp_seasons_sorted[i+1]
            
            score1 = season1['summary_stats']['total_adjusted_points']
            score2 = season2['summary_stats']['total_adjusted_points']
            weeks_played1 = season1['summary_stats']['weeks_played']
            weeks_played2 = season2['summary_stats']['weeks_played']

            # Apply the new condition: player must have played at least MIN_WEEKS_FOR_IMPROVEMENT in both seasons
            if (weeks_played1 >= MIN_WEEKS_FOR_IMPROVEMENT and 
                weeks_played2 >= MIN_WEEKS_FOR_IMPROVEMENT and
                score1 > 0 and score2 > score1): # Ensure previous score is positive and current is an improvement
                improvement = (score2 - score1) / score1
                if improvement > best_mfp_improvement['improvement_percent']:
                    best_mfp_improvement.update({
                        'improvement_percent': improvement,
                        'season1': season1,
                        'season2': season2
                    })
        if best_mfp_improvement['improvement_percent'] > -1:
            mfp_most_improved_leaderboard.append(best_mfp_improvement)

        # Process MFLadies Pinball seasons for improvement
        mflp_seasons_sorted = sorted(player_data['mflp_seasons'], key=lambda x: x['seriesId'])
        best_mflp_improvement = {'player': player_info, 'improvement_percent': -1, 'season1': None, 'season2': None}
        for i in range(len(mflp_seasons_sorted) - 1):
            season1 = mflp_seasons_sorted[i]
            season2 = mflp_seasons_sorted[i+1]
            
            score1 = season1['summary_stats']['total_adjusted_points']
            score2 = season2['summary_stats']['total_adjusted_points']
            weeks_played1 = season1['summary_stats']['weeks_played']
            weeks_played2 = season2['summary_stats']['weeks_played']

            # Apply the new condition: player must have played at least MIN_WEEKS_FOR_IMPROVEMENT in both seasons
            if (weeks_played1 >= MIN_WEEKS_FOR_IMPROVEMENT and 
                weeks_played2 >= MIN_WEEKS_FOR_IMPROVEMENT and
                score1 > 0 and score2 > score1): # Ensure previous score is positive and current is an improvement
                improvement = (score2 - score1) / score1
                if improvement > best_mflp_improvement['improvement_percent']:
                    best_mflp_improvement.update({
                        'improvement_percent': improvement,
                        'season1': season1,
                        'season2': season2
                    })
        if best_mflp_improvement['improvement_percent'] > -1:
            mflp_most_improved_leaderboard.append(best_mflp_improvement)

    mfp_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    mfp_most_improved_leaderboard = mfp_most_improved_leaderboard[:25] # Limit to top 25
    
    mflp_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    mflp_most_improved_leaderboard = mflp_most_improved_leaderboard[:25] # Limit to top 25


    template = env.get_template('leaderboards.html')
    with open(os.path.join(OUTPUT_DIR, 'leaderboards.html'), 'w') as f:
        f.write(template.render(
            mfp_total_points_leaderboard=mfp_total_points_leaderboard,
            mfp_weekly_wins_leaderboard=mfp_weekly_wins_leaderboard,
            mfp_top_4_finishes_leaderboard=mfp_top_4_finishes_leaderboard,
            mfp_best_season_score_leaderboard=mfp_best_season_score_leaderboard,
            mfp_most_improved_leaderboard=mfp_most_improved_leaderboard,
            mflp_total_points_leaderboard=mflp_total_points_leaderboard,
            mflp_weekly_wins_leaderboard=mflp_weekly_wins_leaderboard,
            mflp_top_4_finishes_leaderboard=mflp_top_4_finishes_leaderboard,
            mflp_best_season_score_leaderboard=mflp_best_season_score_leaderboard,
            mflp_most_improved_leaderboard=mflp_most_improved_leaderboard,
            perfect_nights_leaderboard=perfect_nights_leaderboard # Pass perfect nights
        ))
    print("Generated leaderboards.html")


def generate_site(excluded_series_names):
    """Generates the static HTML site."""
    print("Generating static site...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_series_data = load_all_series_data(excluded_series_names)

    if not all_series_data:
        print("\\nNo data found in the 'data' directory.")
        print("Please run the script with fetch_data() enabled to download the data first.")
        return
    
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.abspath(os.path.dirname(__file__)), TEMPLATES_DIR)))
    env.filters['score_color_code'] = score_color_filter # Register the custom filter
    env.filters['format_number'] = format_number_filter # Register the new filter

    template = env.get_template('index.html')
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w') as f:
        f.write(template.render())
    print("Generated index.html")

    generate_seasons_page(env, all_series_data)
    generate_season_pages(env, all_series_data)
    player_categorized_seasons = generate_player_pages(env, all_series_data)
    generate_leaderboards_page(env, all_series_data, player_categorized_seasons)
