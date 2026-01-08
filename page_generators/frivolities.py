import os
from data_processor import find_almost_perfect_nights, find_wooden_nickels, find_biggest_drops, process_game_data, parse_series_name
from config import OUTPUT_DIR

def generate_frivolities_page(env, all_series_data):
    """Generates the frivolities page with perfect nights and other fun stats."""
    print("Generating frivolities.html...")
    
    all_perfect_nights = []
    all_almost_perfect_nights = find_almost_perfect_nights(all_series_data)
    all_wooden_nickels = find_wooden_nickels(all_series_data)
    all_biggest_drops = find_biggest_drops(all_series_data)

    for series_data_raw in all_series_data:
        series_data = series_data_raw['data']
        series_id = series_data['seriesId']
        series_name = series_data['name']
        year, season_name_parsed, league_name_parsed = parse_series_name(series_name)
        
        player_map = {p['playerId']: p['name'] for p in series_data['players']}
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series_data['tournamentIds'])}

        if 'tournamentPoints' in series_data and series_data['tournamentPoints']:
            for tournament_id_str, player_points_map_val in series_data['tournamentPoints'].items():
                current_tournament_id = int(tournament_id_str)
                week_num = tournament_id_to_week_num.get(current_tournament_id)
                if week_num is None:
                    continue

                if isinstance(player_points_map_val, dict):
                    for player_id_str, points_str in player_points_map_val.items():
                        points = float(points_str)
                        player_id = int(player_id_str)
                        
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

    all_perfect_nights.sort(key=lambda x: (x['seriesId'], x['week_num']))
    all_almost_perfect_nights.sort(key=lambda x: (x['seriesId'], x['week_num']))
    all_wooden_nickels.sort(key=lambda x: (x['seriesId'], x['week_num']))
    # all_biggest_drops is already sorted by drop amount

    template = env.get_template('frivolities.html')
    with open(os.path.join(OUTPUT_DIR, 'frivolities.html'), 'w') as f:
        f.write(template.render(
            all_perfect_nights=all_perfect_nights,
            all_almost_perfect_nights=all_almost_perfect_nights,
            all_wooden_nickels=all_wooden_nickels,
            all_biggest_drops=all_biggest_drops[:50] # Limit to top 50
        ))
    print("Generated frivolities.html")
