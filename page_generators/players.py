import os
from collections import defaultdict
from datetime import datetime
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, process_game_data
from api_client import fetch_finals_results
from config import OUTPUT_DIR

# Define the cutoff date for arena data
ARENA_DATA_CUTOFF_DATE = datetime(2024, 1, 1) # Winter 2024 starts roughly here

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
            'original_series_data': series_data_raw
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

        # Determine series start date for grouping
        series_start_date = None
        if 'startDate' in series_data and series_data['startDate']:
            try:
                series_start_date = datetime.strptime(series_data['startDate'].split('T')[0], "%Y-%m-%d")
            except ValueError:
                pass
        
        # Fallback if startDate is missing or parsing fails, use the corrected year
        if not series_start_date and year != "N/A":
             try:
                 # Assume Jan 1st of the year
                 series_start_date = datetime(int(year), 1, 1)
             except ValueError:
                 pass

        game_data = process_game_data(series_data_raw)
        
        # Store game performance with date info
        if series_start_date:
            for player_id, games in game_data['by_machine'].items():
                for game_name, stats in games.items():
                    # We store stats keyed by year to allow filtering later
                    year_key = series_start_date.year
                    if year_key not in all_players_game_performance[player_id][game_name]:
                         all_players_game_performance[player_id][game_name][year_key] = defaultdict(int)
                    
                    all_players_game_performance[player_id][game_name][year_key]['1st_place'] += stats['1st']
                    all_players_game_performance[player_id][game_name][year_key]['2nd_place'] += stats['2nd_4p'] + stats['2nd_3p']
                    all_players_game_performance[player_id][game_name][year_key]['3rd_place'] += stats['3rd_4p'] + stats['4th_combined']
                    all_players_game_performance[player_id][game_name][year_key]['4th_place'] += stats['4th_combined'] # Note: 4th_combined includes 3rd in 3p, but here we want 4th place specifically?
                    # Wait, process_game_data logic:
                    # 3rd place in 4p -> '3rd_4p'
                    # 3rd place in 3p -> '4th_combined' (weird naming in process_game_data, let's check)
                    # 4th place in 4p -> '4th_combined'
                    
                    # Let's re-read process_game_data in data_processor.py to be sure.
                    # if position == 3:
                    #   if num_players == 4: by_machine...['3rd_4p'] += 1
                    #   elif num_players == 3: by_machine...['4th_combined'] += 1
                    # if position == 4:
                    #   if num_players == 4: by_machine...['4th_combined'] += 1
                    
                    # So '4th_combined' actually means "Last place in a 3 or 4 player game" effectively?
                    # Or rather "1 point game"?
                    # In standard scoring:
                    # 4p: 7, 5, 3, 1
                    # 3p: 7, 4, 1
                    
                    # So 3rd in 3p gets 1 point. 4th in 4p gets 1 point.
                    # 3rd in 4p gets 3 points.
                    
                    # The user wants: 1st, 2nd, 3rd, 4th.
                    # 1st is clear.
                    # 2nd is clear (2nd_4p + 2nd_3p).
                    # 3rd is 3rd_4p.
                    # 4th is 4th_combined (which includes 3rd in 3p and 4th in 4p).
                    
                    # Let's map them:
                    # 1st Place: stats['1st']
                    # 2nd Place: stats['2nd_4p'] + stats['2nd_3p']
                    # 3rd Place: stats['3rd_4p']
                    # 4th Place (or Last): stats['4th_combined']
                    
                    # Wait, 3rd place in a 3-player game is technically 3rd place, but gets 1 point (like 4th).
                    # The user prompt says: "We should have 1st, 2nd, 2nd in a 3 player group, 3rd and 4th (3rd in 3player group)"
                    # Wait, "2nd, 2nd in a 3 player group" -> implies separating them?
                    # "3rd and 4th (3rd in 3player group)" -> implies combining 3rd(4p) and 4th(4p)/3rd(3p)?
                    # Or maybe "3rd" column and "4th" column.
                    
                    # Let's re-read carefully: "We should have 1st, 2nd, 2nd in a 3 player group, 3rd and 4th (3rd in 3player group)"
                    # This sounds like 5 columns?
                    # 1. 1st
                    # 2. 2nd (4p)
                    # 3. 2nd (3p)
                    # 4. 3rd (4p)
                    # 5. 4th (4p) + 3rd (3p) -> This is what '4th_combined' currently tracks in data_processor.
                    
                    # So we need to track these separately in data_processor if they aren't already.
                    # process_game_data currently tracks:
                    # 1st
                    # 2nd_4p
                    # 2nd_3p
                    # 3rd_4p
                    # 4th_combined (3rd in 3p AND 4th in 4p)
                    
                    # So we have all the buckets we need in `stats`.
                    # We just need to aggregate them correctly here.
                    
                    all_players_game_performance[player_id][game_name][year_key]['1st'] += stats['1st']
                    all_players_game_performance[player_id][game_name][year_key]['2nd'] += stats['2nd_4p']
                    all_players_game_performance[player_id][game_name][year_key]['2nd_3p'] += stats['2nd_3p']
                    all_players_game_performance[player_id][game_name][year_key]['3rd'] += stats['3rd_4p']
                    all_players_game_performance[player_id][game_name][year_key]['4th'] += stats['4th_combined']
                    all_players_game_performance[player_id][game_name][year_key]['total_plays'] += stats['total_plays']

        finals_tournament_ids = None
        if league_name_parsed in load_finals_mapping() and year != "N/A" and season_name_parsed != "N/A":
            key = f"{season_name_parsed} {year}"
            finals_tournament_ids = load_finals_mapping()[league_name_parsed].get(key)
        
        finals_player_positions = {}
        if finals_tournament_ids:
            finals_standings = fetch_finals_results(finals_tournament_ids)
            if finals_standings:
                finals_player_positions = {res['playerId']: res['position'] for res in finals_standings}

        weekly_winners = {}
        if 'tournamentPoints' in series_data and isinstance(series_data['tournamentPoints'], dict):
            for tournament_id, player_points_map in series_data['tournamentPoints'].items():
                if player_points_map:
                    winner_id = max(player_points_map, key=lambda p_id: float(player_points_map[p_id]))
                    weekly_winners[tournament_id] = int(winner_id)

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
            
            if 'tournamentPoints' in series_data and isinstance(series_data['tournamentPoints'], dict):
                for tournament_id_str, player_points_map in series_data['tournamentPoints'].items():
                    if str(player_id) in player_points_map:
                        points = float(player_points_map[str(player_id)])
                        weekly_performance_raw.append({'tournament_id': int(tournament_id_str), 'points': points})
                        total_raw_points += points

            weekly_wins = sum(1 for winner_id in weekly_winners.values() if winner_id == player_id)
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
                    'weekly_wins': weekly_wins,
                    'average_points_per_week': round(average_points_per_week, 2),
                    'best_week_score': top_6_scores[0] if top_6_scores and top_6_scores[0] is not None else 0.0,
                    'top_6_scores': top_6_scores,
                    'game_outcomes': dict(player_game_stats)
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
        
        # Convert defaultdicts to dicts for serialization
        serializable_game_perf = {}
        for game_name, years_data in all_players_game_performance[player_id].items():
            serializable_game_perf[game_name] = {}
            for year_key, stats in years_data.items():
                serializable_game_perf[game_name][year_key] = dict(stats)
        
        data['game_performance'] = serializable_game_perf

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
        
        # Pass the specific player's chart data to the template
        player_chart_data = all_players_chart_data.get(player_id, {})

        with open(os.path.join(OUTPUT_DIR, f"player_{player_id}.html"), 'w') as f:
            f.write(player_template.render(
                player=player,
                mfp_seasons=data['mfp_seasons'],
                mflp_seasons=data['mflp_seasons'],
                game_performance=data['game_performance'],
                arena_cutoff_date=ARENA_DATA_CUTOFF_DATE.strftime("%B %Y"),
                player_chart_data=player_chart_data, # Pass chart data
                all_players_chart_data=all_players_chart_data # Pass all data for comparison
            ))
        print(f"Generated player_{player_id}.html")

    players_list_template = env.get_template('players.html')
    with open(os.path.join(OUTPUT_DIR, 'players.html'), 'w') as f:
        f.write(players_list_template.render(players=players_list))
    print("Generated players.html")
    
    return player_categorized_seasons, all_players_chart_data
