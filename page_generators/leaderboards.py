import os
from copy import deepcopy
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, find_almost_perfect_nights, process_game_data
from api_client import fetch_finals_results
from config import OUTPUT_DIR, MIN_WEEKS_FOR_IMPROVEMENT

def generate_leaderboards_page(env, all_series_data, player_categorized_seasons):
    """Generates the all-time leaderboards page, separated by league type."""
    print("Generating leaderboards.html...")
    
    mfp_players_stats = {}
    mflp_players_stats = {}
    
    all_winning_scores = []
    all_perfect_nights = []

    all_almost_perfect_nights = find_almost_perfect_nights(all_series_data)

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
            'original_series_data': series_data_raw
        })
    
    corrected_temp_season_entries = apply_year_corrections_to_seasons_list(temp_season_entries)
    corrected_seasons_map = {s['seriesId']: s for s in corrected_temp_season_entries}

    for series_data_raw in all_series_data:
        series_data = series_data_raw['data']
        series_id = series_data['seriesId']
        
        game_data = process_game_data(series_data_raw)
        
        corrected_season_info = corrected_seasons_map.get(series_id, {})
        year = corrected_season_info.get('year', 'N/A')
        season_name_parsed = corrected_season_info.get('season_name', 'N/A')
        league_name_parsed = corrected_season_info.get('league_name', 'Other')

        target_stats_dict = None
        if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
            target_stats_dict = mfp_players_stats
        elif "Monterey Flipper Ladies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
            target_stats_dict = mflp_players_stats
        
        if target_stats_dict is not None:
            for player_id, player_game_stats in game_data['by_player'].items():
                if player_id not in target_stats_dict:
                    target_stats_dict[player_id] = {
                        'playerId': player_id,
                        'name': '',
                        'ifpaId': None,
                        'total_adjusted_points': 0.0,
                        'total_raw_points': 0.0,
                        'top_4_finishes': {1: 0, 2: 0, 3: 0, 4: 0},
                        'seasons_played_count': 0,
                        'total_weeks_played': 0,
                        'weekly_wins': 0,
                        'average_points_per_week': 0.0,
                        'total_games_won': 0
                    }
                target_stats_dict[player_id]['total_games_won'] += player_game_stats.get('1st', 0)

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
                        'total_raw_points': 0.0,
                        'top_4_finishes': {1: 0, 2: 0, 3: 0, 4: 0},
                        'seasons_played_count': 0,
                        'total_weeks_played': 0,
                        'weekly_wins': 0,
                        'average_points_per_week': 0.0,
                        'total_games_won': 0
                    }
                
                target_stats_dict[player_id]['name'] = player_name
                if ifpa_id:
                    target_stats_dict[player_id]['ifpaId'] = ifpa_id

                player_standing = next((s for s in series_data['standings'] if s['playerId'] == player_id), None)
                
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
        
        player_map = {p['playerId']: p['name'] for p in series_data['players']}
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series_data['tournamentIds'])}

        if 'tournamentPoints' in series_data and series_data['tournamentPoints']:
            for tournament_id_str, player_points_map_val in series_data['tournamentPoints'].items():
                current_tournament_id = int(tournament_id_str)
                week_num = tournament_id_to_week_num.get(current_tournament_id)
                if week_num is None:
                    continue

                if isinstance(player_points_map_val, dict):
                    weekly_winner_id = None
                    max_score = -1
                    for player_id_str, points_str in player_points_map_val.items():
                        points = float(points_str)
                        player_id = int(player_id_str)
                        
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
                                'seriesName': series_data['name'],
                                'year': year,
                                'season_name': season_name_parsed,
                                'week_num': week_num,
                                'league_type': 'Combined'
                            }
                            if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
                                perfect_night_entry['league_type'] = 'MFP'
                            elif "MFLadies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
                                perfect_night_entry['league_type'] = 'MFLP'
                            
                            all_perfect_nights.append(perfect_night_entry)
                    
                    if weekly_winner_id and target_stats_dict and weekly_winner_id in target_stats_dict:
                        target_stats_dict[weekly_winner_id]['weekly_wins'] += 1

    for stats in list(mfp_players_stats.values()) + list(mflp_players_stats.values()):
        if stats['total_weeks_played'] > 0:
            stats['average_points_per_week'] = stats['total_raw_points'] / stats['total_weeks_played']

    all_perfect_nights.sort(key=lambda x: (x['seriesId'], x['week_num']))

    mfp_leaderboard_data = list(mfp_players_stats.values())
    mfp_total_points_leaderboard = sorted(mfp_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    mfp_top_4_finishes_leaderboard = sorted([p for p in mfp_leaderboard_data if sum(p['top_4_finishes'].values()) > 0], key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    mflp_leaderboard_data = list(mflp_players_stats.values())
    mflp_total_points_leaderboard = sorted(mflp_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    mflp_top_4_finishes_leaderboard = sorted([p for p in mflp_leaderboard_data if sum(p['top_4_finishes'].values()) > 0], key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    combined_players_stats = deepcopy(mfp_players_stats)
    for player_id, stats in mflp_players_stats.items():
        if player_id in combined_players_stats:
            combined_players_stats[player_id]['total_adjusted_points'] += stats['total_adjusted_points']
            combined_players_stats[player_id]['total_raw_points'] += stats['total_raw_points']
            combined_players_stats[player_id]['seasons_played_count'] += stats['seasons_played_count']
            combined_players_stats[player_id]['total_weeks_played'] += stats['total_weeks_played']
            combined_players_stats[player_id]['weekly_wins'] += stats['weekly_wins']
            combined_players_stats[player_id]['total_games_won'] += stats.get('total_games_won', 0)
            for i in range(1, 5):
                combined_players_stats[player_id]['top_4_finishes'][i] += stats['top_4_finishes'][i]
        else:
            combined_players_stats[player_id] = stats
    
    for stats in combined_players_stats.values():
        if stats['total_weeks_played'] > 0:
            stats['average_points_per_week'] = stats['total_raw_points'] / stats['total_weeks_played']

    combined_leaderboard_data = list(combined_players_stats.values())
    combined_total_points_leaderboard = sorted(combined_leaderboard_data, key=lambda x: x['total_raw_points'], reverse=True)[:25]
    combined_top_4_finishes_leaderboard = sorted([p for p in combined_leaderboard_data if sum(p['top_4_finishes'].values()) > 0], key=lambda x: (x['top_4_finishes'][1], x['top_4_finishes'][2], x['top_4_finishes'][3], x['top_4_finishes'][4]), reverse=True)

    mfp_most_improved_leaderboard, mflp_most_improved_leaderboard, combined_most_improved_leaderboard = [], [], []
    mfp_top_seasons, mflp_top_seasons, combined_top_seasons = [], [], []

    for player_id, player_data in player_categorized_seasons.items():
        player_info = player_data['player_info']
        
        mfp_seasons_sorted = sorted(player_data['mfp_seasons'], key=lambda x: x['seriesId'])
        best_mfp_improvement = {'player': player_info, 'improvement_percent': -1, 'season1': None, 'season2': None}
        for i, season in enumerate(mfp_seasons_sorted):
            if i > 0:
                season1 = mfp_seasons_sorted[i-1]
                season2 = season
                score1 = season1['summary_stats']['total_adjusted_points']
                score2 = season2['summary_stats']['total_adjusted_points']
                weeks_played1 = season1['summary_stats']['weeks_played']
                weeks_played2 = season2['summary_stats']['weeks_played']

                if (weeks_played1 >= MIN_WEEKS_FOR_IMPROVEMENT and weeks_played2 >= MIN_WEEKS_FOR_IMPROVEMENT and score1 > 0 and score2 > score1):
                    improvement = (score2 - score1) / score1
                    if improvement > best_mfp_improvement['improvement_percent']:
                        best_mfp_improvement.update({'improvement_percent': improvement, 'season1': season1, 'season2': season2})
            
            mfp_top_seasons.append({'player': player_info, 'season': season, 'score': season['summary_stats']['total_adjusted_points'], 'game_outcomes': season['summary_stats']['game_outcomes'], 'weekly_wins': season['summary_stats']['weekly_wins']})

        if best_mfp_improvement['improvement_percent'] > -1:
            mfp_most_improved_leaderboard.append(best_mfp_improvement)

        mflp_seasons_sorted = sorted(player_data['mflp_seasons'], key=lambda x: x['seriesId'])
        best_mflp_improvement = {'player': player_info, 'improvement_percent': -1, 'season1': None, 'season2': None}
        for i, season in enumerate(mflp_seasons_sorted):
            if i > 0:
                season1 = mflp_seasons_sorted[i-1]
                season2 = season
                score1 = season1['summary_stats']['total_adjusted_points']
                score2 = season2['summary_stats']['total_adjusted_points']
                weeks_played1 = season1['summary_stats']['weeks_played']
                weeks_played2 = season2['summary_stats']['weeks_played']

                if (weeks_played1 >= MIN_WEEKS_FOR_IMPROVEMENT and weeks_played2 >= MIN_WEEKS_FOR_IMPROVEMENT and score1 > 0 and score2 > score1):
                    improvement = (score2 - score1) / score1
                    if improvement > best_mflp_improvement['improvement_percent']:
                        best_mflp_improvement.update({'improvement_percent': improvement, 'season1': season1, 'season2': season2})

            mflp_top_seasons.append({'player': player_info, 'season': season, 'score': season['summary_stats']['total_adjusted_points'], 'game_outcomes': season['summary_stats']['game_outcomes'], 'weekly_wins': season['summary_stats']['weekly_wins']})

        if best_mflp_improvement['improvement_percent'] > -1:
            mflp_most_improved_leaderboard.append(best_mflp_improvement)

        all_seasons_sorted = sorted(player_data['mfp_seasons'] + player_data['mflp_seasons'], key=lambda x: x['seriesId'])
        best_combined_improvement = {'player': player_info, 'improvement_percent': -1, 'season1': None, 'season2': None}
        for i, season in enumerate(all_seasons_sorted):
            if i > 0:
                season1 = all_seasons_sorted[i-1]
                season2 = season
                score1 = season1['summary_stats']['total_adjusted_points']
                score2 = season2['summary_stats']['total_adjusted_points']
                weeks_played1 = season1['summary_stats']['weeks_played']
                weeks_played2 = season2['summary_stats']['weeks_played']

                if (weeks_played1 >= MIN_WEEKS_FOR_IMPROVEMENT and weeks_played2 >= MIN_WEEKS_FOR_IMPROVEMENT and score1 > 0 and score2 > score1):
                    improvement = (score2 - score1) / score1
                    if improvement > best_combined_improvement['improvement_percent']:
                        best_combined_improvement.update({'improvement_percent': improvement, 'season1': season1, 'season2': season2})

            combined_top_seasons.append({'player': player_info, 'season': season, 'score': season['summary_stats']['total_adjusted_points'], 'game_outcomes': season['summary_stats']['game_outcomes'], 'weekly_wins': season['summary_stats']['weekly_wins']})

        if best_combined_improvement['improvement_percent'] > -1:
            combined_most_improved_leaderboard.append(best_combined_improvement)

    mfp_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    mflp_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)
    combined_most_improved_leaderboard.sort(key=lambda x: x['improvement_percent'], reverse=True)

    mfp_top_seasons.sort(key=lambda x: x['score'], reverse=True)
    mflp_top_seasons.sort(key=lambda x: x['score'], reverse=True)
    combined_top_seasons.sort(key=lambda x: x['score'], reverse=True)

    template = env.get_template('leaderboards.html')
    with open(os.path.join(OUTPUT_DIR, 'leaderboards.html'), 'w') as f:
        f.write(template.render(
            mfp_total_points_leaderboard=mfp_total_points_leaderboard[:25],
            mfp_top_4_finishes_leaderboard=mfp_top_4_finishes_leaderboard,
            mfp_top_seasons_leaderboard=mfp_top_seasons[:25],
            mfp_most_improved_leaderboard=mfp_most_improved_leaderboard[:25],
            mflp_total_points_leaderboard=mflp_total_points_leaderboard[:25],
            mflp_top_4_finishes_leaderboard=mflp_top_4_finishes_leaderboard,
            mflp_top_seasons_leaderboard=mflp_top_seasons[:25],
            mflp_most_improved_leaderboard=mflp_most_improved_leaderboard[:25],
            combined_total_points_leaderboard=combined_total_points_leaderboard[:25],
            combined_top_4_finishes_leaderboard=combined_top_4_finishes_leaderboard,
            combined_top_seasons_leaderboard=combined_top_seasons[:25],
            combined_most_improved_leaderboard=combined_most_improved_leaderboard[:25],
            all_perfect_nights=all_perfect_nights,
            all_almost_perfect_nights=all_almost_perfect_nights
        ))
    print("Generated leaderboards.html")
