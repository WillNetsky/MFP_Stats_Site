import os
from collections import defaultdict
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, process_game_data
from api_client import fetch_finals_results
from config import OUTPUT_DIR

def generate_player_pages(env, all_series_data):
    """Generates individual player pages and a main players list page."""
    unique_players = {}
    player_categorized_seasons = {}
    all_players_game_performance = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
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
        })
    
    corrected_temp_season_entries = apply_year_corrections_to_seasons_list(temp_season_entries)
    corrected_seasons_map = {s['seriesId']: s for s in corrected_temp_season_entries}

    for series_data_raw in all_series_data:
        series_data = series_data_raw['data']
        series_id = series_data['seriesId']
        
        corrected_info = corrected_seasons_map.get(series_id)
        year = corrected_info['year']
        season_name_parsed = corrected_info['season_name']
        league_name_parsed = corrected_info['league_name']

        game_data = process_game_data(series_data_raw)
        
        for player_id, games in game_data['by_machine'].items():
            for game_name, stats in games.items():
                all_players_game_performance[player_id][game_name]['1st_place'] += stats['1st_place']
                all_players_game_performance[player_id][game_name]['2nd_place'] += stats['2nd_place']
                all_players_game_performance[player_id][game_name]['3rd_place'] += stats['3rd_place']
                all_players_game_performance[player_id][game_name]['total_plays'] += stats['total_plays']

        finals_tournament_ids = None
        if league_name_parsed in load_finals_mapping() and year != "N/A" and season_name_parsed != "N/A":
            key = f"{season_name_parsed} {year}"
            finals_tournament_ids = load_finals_mapping()[league_name_parsed].get(key)
        
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
            
            player_standing = next((s for s in series_data['standings'] if s['playerId'] == player_id), None)
            
            qualifying_position = player_standing['position'] if player_standing else 'N/A'
            final_position = qualifying_position
            played_in_finals = player_id in finals_player_positions
            
            if played_in_finals:
                final_position = finals_player_positions[player_id]

            weekly_performance_raw = []
            total_raw_points = 0.0
            
            if 'tournamentPoints' in series_data:
                for tournament_id_str, player_points_map in series_data['tournamentPoints'].items():
                    if str(player_id) in player_points_map:
                        points = float(player_points_map[str(player_id)])
                        weekly_performance_raw.append({'tournament_id': int(tournament_id_str), 'points': points})
                        total_raw_points += points

            player_game_stats = game_data['by_player'].get(player_id, defaultdict(int))

            weekly_performance_sorted = sorted(weekly_performance_raw, key=lambda x: x['points'], reverse=True)
            top_6_scores = [week['points'] for week in weekly_performance_sorted[:6]]
            top_6_scores.extend([None] * (6 - len(top_6_scores)))

            num_weeks_played = len(weekly_performance_raw)
            average_points_per_week = total_raw_points / num_weeks_played if num_weeks_played > 0 else 0

            season_entry = {
                'seriesId': series_id,
                'seriesName': series_data['name'],
                'year': year,
                'season_name': season_name_parsed,
                'league_name': league_name_parsed,
                'summary_stats': {
                    'final_position': final_position,
                    'qualifying_position': qualifying_position,
                    'played_in_finals': played_in_finals,
                    'total_raw_points': round(total_raw_points, 2),
                    'total_adjusted_points': player_standing['pointsAdjusted'] if player_standing else 0,
                    'weeks_played': num_weeks_played,
                    'average_points_per_week': round(average_points_per_week, 2),
                    'best_week_score': top_6_scores[0] if top_6_scores and top_6_scores[0] is not None else 0.0,
                    'top_6_scores': top_6_scores,
                    'game_outcomes': player_game_stats
                }
            }

            if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
                player_categorized_seasons[player_id]['mfp_seasons'].append(season_entry)
            elif "Monterey Flipper Ladies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
                player_categorized_seasons[player_id]['mflp_seasons'].append(season_entry)

    players_list = list(unique_players.values())
    
    for player_id, data in player_categorized_seasons.items():
        data['mfp_seasons'].sort(key=lambda x: x['seriesId'], reverse=True)
        data['mflp_seasons'].sort(key=lambda x: x['seriesId'], reverse=True)
        data['game_performance'] = dict(all_players_game_performance[player_id])

    all_players_chart_data = {}
    for player_id, player_data in player_categorized_seasons.items():
        all_players_chart_data[player_id] = {
            'name': player_data['player_info']['name'],
            'mfp_seasons_data': [],
            'mflp_seasons_data': []
        }
        sorted_mfp_seasons = sorted(player_data['mfp_seasons'], key=lambda x: (x['year'] if x['year'] != 'N/A' else '9999', x['seriesId']))
        for season in sorted_mfp_seasons:
            all_players_chart_data[player_id]['mfp_seasons_data'].append({
                'label': f"{season['season_name']} {season['year']}",
                'stats': season['summary_stats']
            })
        sorted_mflp_seasons = sorted(player_data['mflp_seasons'], key=lambda x: (x['year'] if x['year'] != 'N/A' else '9999', x['seriesId']))
        for season in sorted_mflp_seasons:
            all_players_chart_data[player_id]['mflp_seasons_data'].append({
                'label': f"{season['season_name']} {season['year']}",
                'stats': season['summary_stats']
            })

    player_template = env.get_template('player.html')
    for player_id, data in player_categorized_seasons.items():
        player = data['player_info']
        
        with open(os.path.join(OUTPUT_DIR, f"player_{player_id}.html"), 'w') as f:
            f.write(player_template.render(
                player=player,
                mfp_seasons=data['mfp_seasons'],
                mflp_seasons=data['mflp_seasons'],
                game_performance=data['game_performance'],
            ))
        print(f"Generated player_{player_id}.html")

    players_list_template = env.get_template('players.html')
    with open(os.path.join(OUTPUT_DIR, 'players.html'), 'w') as f:
        f.write(players_list_template.render(players=players_list))
    print("Generated players.html")
    
    return player_categorized_seasons, all_players_chart_data
