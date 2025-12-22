import os
from copy import deepcopy
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, find_almost_perfect_nights
from api_client import fetch_finals_results
from config import OUTPUT_DIR, MIN_WEEKS_FOR_IMPROVEMENT

def generate_leaderboards_page(env, all_series_data, player_categorized_seasons):
    """Generates the all-time leaderboards page, separated by league type."""
    print("Generating leaderboards.html...")
    
    mfp_players_stats = {}
    mflp_players_stats = {}
    
    # Track all winning scores to determine the global minimum winning score
    all_winning_scores = []
    all_perfect_nights = [] # Consolidated list for perfect nights

    # Call the new function to find almost perfect nights
    all_almost_perfect_nights = find_almost_perfect_nights(all_series_data)

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
        elif "Monterey Flipper Ladies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
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
                        'weekly_wins': 0, # New field
                        'average_points_per_week': 0.0 # New field
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
                            perfect_night_entry = {
                                'playerId': player_id,
                                'name': player_name,
                                'seriesId': series_id,
                                'seriesName': series_name,
                                'year': year,
                                'season_name': season_name_parsed,
                                'week_num': week_num,
                                'league_type': 'Combined' # Default to combined
                            }
                            if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
                                perfect_night_entry['league_type'] = 'MFP'
                            elif "MFLadies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
                                perfect_night_entry['league_type'] = 'MFLP'
                            
                            all_perfect_nights.append(perfect_night_entry)
                    
                    if weekly_winner_id and target_stats_dict and weekly_winner_id in target_stats_dict:
                        target_stats_dict[weekly_winner_id]['weekly_wins'] += 1

    # Calculate average points per week for each player
    for player_id, stats in mfp_players_stats.items():
        if stats['total_weeks_played'] > 0:
            stats['average_points_per_week'] = stats['total_raw_points'] / stats['total_weeks_played']
    for player_id, stats in mflp_players_stats.items():
        if stats['total_weeks_played'] > 0:
            stats['average_points_per_week'] = stats['total_raw_points'] / stats['total_weeks_played']

    # Sort all perfect nights by seriesId then week_num
    all_perfect_nights.sort(key=lambda x: (x['seriesId'], x['week_num']))

    # Determine global minimum winning score
    min_winning_score = min(all_winning_scores) if all_winning_scores else 0.0

    # --- MFP Leaderboards ---
    mfp_leaderboard_data = list(mfp_players_stats.values())
    # Combine total points and weekly wins into a single leaderboard, sorted by total_raw_points
    mfp_total_points_leaderboard = sorted(mfp_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    
    mfp_top_4_finishes_leaderboard = [p for p in mfp_leaderboard_data if sum(p['top_4_finishes'].values()) > 0]
    mfp_top_4_finishes_leaderboard.sort(key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    mfp_best_season_score_leaderboard = [p for p in mfp_leaderboard_data if p['best_season_score']['score'] >= min_winning_score and isinstance(p['best_season_score']['final_position'], int) and p['best_season_score']['final_position'] <= 10]
    mfp_best_season_score_leaderboard.sort(key=lambda x: x['best_season_score']['score'], reverse=True)

    # --- MFLadies Pinball Leaderboards ---
    mflp_leaderboard_data = list(mflp_players_stats.values())
    # Combine total points and weekly wins into a single leaderboard, sorted by total_raw_points
    mflp_total_points_leaderboard = sorted(mflp_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    
    mflp_top_4_finishes_leaderboard = [p for p in mflp_leaderboard_data if sum(p['top_4_finishes'].values()) > 0]
    mflp_top_4_finishes_leaderboard.sort(key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    mflp_best_season_score_leaderboard = [p for p in mflp_leaderboard_data if p['best_season_score']['score'] >= min_winning_score and isinstance(p['best_season_score']['final_position'], int) and p['best_season_score']['final_position'] <= 10]
    mflp_best_season_score_leaderboard.sort(key=lambda x: x['best_season_score']['score'], reverse=True)

    # --- Combined Leaderboards ---
    combined_players_stats = deepcopy(mfp_players_stats)
    for player_id, stats in mflp_players_stats.items():
        if player_id in combined_players_stats:
            combined_players_stats[player_id]['total_adjusted_points'] += stats['total_adjusted_points']
            combined_players_stats[player_id]['total_raw_points'] += stats['total_raw_points']
            combined_players_stats[player_id]['seasons_played_count'] += stats['seasons_played_count']
            combined_players_stats[player_id]['total_weeks_played'] += stats['total_weeks_played']
            combined_players_stats[player_id]['weekly_wins'] += stats['weekly_wins']
            for i in range(1, 5):
                combined_players_stats[player_id]['top_4_finishes'][i] += stats['top_4_finishes'][i]
            if stats['best_season_score']['score'] > combined_players_stats[player_id]['best_season_score']['score']:
                combined_players_stats[player_id]['best_season_score'] = stats['best_season_score']
        else:
            combined_players_stats[player_id] = stats
    
    for player_id, stats in combined_players_stats.items():
        if stats['total_weeks_played'] > 0:
            stats['average_points_per_week'] = stats['total_raw_points'] / stats['total_weeks_played']

    combined_leaderboard_data = list(combined_players_stats.values())
    # Combine total points and weekly wins into a single leaderboard, sorted by total_raw_points
    combined_total_points_leaderboard = sorted(combined_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    
    combined_top_4_finishes_leaderboard = [p for p in combined_leaderboard_data if sum(p['top_4_finishes'].values()) > 0]
    combined_top_4_finishes_leaderboard.sort(key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)
    combined_best_season_score_leaderboard = [p for p in combined_leaderboard_data if p['best_season_score']['score'] >= min_winning_score and isinstance(p['best_season_score']['final_position'], int) and p['best_season_score']['final_position'] <= 10]
    combined_best_season_score_leaderboard.sort(key=lambda x: x['best_season_score']['score'], reverse=True)


    # --- Most Improved Player Leaderboards ---
    mfp_most_improved_leaderboard = []
    mflp_most_improved_leaderboard = []
    combined_most_improved_leaderboard = []

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

        # Process Combined seasons for improvement
        all_seasons_sorted = sorted(player_data['mfp_seasons'] + player_data['mflp_seasons'], key=lambda x: x['seriesId'])
        best_combined_improvement = {'player': player_info, 'improvement_percent': -1, 'season1': None, 'season2': None}
        for i in range(len(all_seasons_sorted) - 1):
            season1 = all_seasons_sorted[i]
            season2 = all_seasons_sorted[i+1]
            
            score1 = season1['summary_stats']['total_adjusted_points']
            score2 = season2['summary_stats']['total_adjusted_points']
            weeks_played1 = season1['summary_stats']['weeks_played']
            weeks_played2 = season2['summary_stats']['weeks_played']

            # Apply the new condition: player must have played at least MIN_WEEKS_FOR_IMPROVEMENT in both seasons
            if (weeks_played1 >= MIN_WEEKS_FOR_IMPROVEMENT and 
                weeks_played2 >= MIN_WEEKS_FOR_IMPROVEMENT and
                score1 > 0 and score2 > score1): # Ensure previous score is positive and current is an improvement
                improvement = (score2 - score1) / score1
                if improvement > best_combined_improvement['improvement_percent']:
                    best_combined_improvement.update({
                        'improvement_percent': improvement,
                        'season1': season1,
                        'season2': season2
                    })
        if best_combined_improvement['improvement_percent'] > -1:
            combined_most_improved_leaderboard.append(best_combined_improvement)


    mfp_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    mfp_most_improved_leaderboard = mfp_most_improved_leaderboard[:25] # Limit to top 25
    
    mflp_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    mflp_most_improved_leaderboard = mflp_most_improved_leaderboard[:25] # Limit to top 25

    combined_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    combined_most_improved_leaderboard = combined_most_improved_leaderboard[:25]


    template = env.get_template('leaderboards.html')
    with open(os.path.join(OUTPUT_DIR, 'leaderboards.html'), 'w') as f:
        f.write(template.render(
            mfp_total_points_leaderboard=mfp_total_points_leaderboard,
            mfp_top_4_finishes_leaderboard=mfp_top_4_finishes_leaderboard,
            mfp_best_season_score_leaderboard=mfp_best_season_score_leaderboard,
            mfp_most_improved_leaderboard=mfp_most_improved_leaderboard,
            mflp_total_points_leaderboard=mflp_total_points_leaderboard,
            mflp_top_4_finishes_leaderboard=mflp_top_4_finishes_leaderboard,
            mflp_best_season_score_leaderboard=mflp_best_season_score_leaderboard,
            mflp_most_improved_leaderboard=mflp_most_improved_leaderboard,
            combined_total_points_leaderboard=combined_total_points_leaderboard,
            combined_top_4_finishes_leaderboard=combined_top_4_finishes_leaderboard,
            combined_best_season_score_leaderboard=combined_best_season_score_leaderboard,
            combined_most_improved_leaderboard=combined_most_improved_leaderboard,
            all_perfect_nights=all_perfect_nights, # Pass the consolidated list
            all_almost_perfect_nights=all_almost_perfect_nights # Pass the new list
        ))
    print("Generated leaderboards.html")
