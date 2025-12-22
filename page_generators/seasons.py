import os
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list
from api_client import fetch_finals_results
from config import OUTPUT_DIR
from page_generators.helpers import get_qualification_threshold

def generate_seasons_page(env, all_series_data):
    """Generates the seasons.html page, separated by league type."""
    print("Generating seasons.html...")
    template = env.get_template('seasons.html')

    mfp_seasons_raw = []
    mflp_seasons_raw = []
    finals_mapping = load_finals_mapping()
    all_years = set()

    # Map seriesId to its full raw data for easy lookup
    series_data_map = {s['data']['seriesId']: s for s in all_series_data}

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
            'fourth_place_player': None,
            'qualified_players_count': 0, # Initialize here
            'qualification_threshold': 0 # Initialize here
        }

        if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
            mfp_seasons_raw.append(season_entry)
        elif "Monterey Flipper Ladies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
            mflp_seasons_raw.append(season_entry)
    
    # Apply year corrections to the collected lists
    mfp_seasons = apply_year_corrections_to_seasons_list(mfp_seasons_raw)
    mflp_seasons = apply_year_corrections_to_seasons_list(mflp_seasons_raw)

    # Now, with corrected years, determine finals status and top 4 players and qualified players count
    for season_list in [mfp_seasons, mflp_seasons]:
        for season_entry in season_list:
            league_name = season_entry['league_name']
            year = season_entry['year']
            season_name = season_entry['season_name']
            series_id = season_entry['seriesId']
            all_years.add(year)

            # Determine finals status
            finals_tournament_ids = None
            if league_name in finals_mapping and year != "N/A" and season_name != "N/A":
                key = f"{season_name} {year}"
                finals_tournament_ids = finals_mapping[league_name].get(key)
            
            season_entry['has_finals'] = "Yes" if finals_tournament_ids else "No"
            
            # Extract top 4 players from the original series data
            original_series_data_for_top4 = series_data_map.get(series_id) # Use the map for lookup
            if original_series_data_for_top4:
                series_details = original_series_data_for_top4['data']
                player_map = {p['playerId']: p['name'] for p in series_details['players']}
                
                top_players_standings = []
                if season_entry['has_finals'] == "Yes" and finals_tournament_ids:
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
                        print(f"WARNING: Finals data for Season: {season_entry['seriesName']} (ID: {series_id}) is empty. Falling back to qualifying standings.")
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
                        season_entry['first_place_player'] = {'playerId': player_id, 'name': player_name}
                    elif i == 1:
                        season_entry['second_place_player'] = {'playerId': player_id, 'name': player_name}
                    elif i == 2:
                            season_entry['third_place_player'] = {'playerId': player_id, 'name': player_name}
                    elif i == 3:
                        season_entry['fourth_place_player'] = {'playerId': player_id, 'name': player_name}

                # Calculate qualified players count
                qualification_threshold = get_qualification_threshold(year, season_name)
                season_entry['qualification_threshold'] = qualification_threshold
                qualified_player_ids = set()
                for player_info in series_details['players']:
                    player_id = player_info['playerId']
                    weeks_played = 0
                    if 'tournamentPoints' in series_details:
                        for tournament_id_str, player_points_map in series_details['tournamentPoints'].items():
                            if str(player_id) in player_points_map:
                                weeks_played += 1
                    if weeks_played >= qualification_threshold:
                        qualified_player_ids.add(player_id)
                season_entry['qualified_players_count'] = len(qualified_player_ids)


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
                for tournament_id_str, player_points_map in series['tournamentPoints'].items():
                    if str(player_id) in player_points_map:
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
