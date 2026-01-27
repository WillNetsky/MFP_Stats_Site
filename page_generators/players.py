import os
from collections import defaultdict
from datetime import datetime
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, process_game_data, extract_year_from_series_data
from api_client import fetch_finals_results
from config import OUTPUT_DIR

# Define the cutoff date for arena data
ARENA_DATA_CUTOFF_DATE = datetime(2024, 1, 1) # Winter 2024 starts roughly here

MIN_GAMES_FOR_MACHINE_HIGHLIGHT = 5


def _build_player_bio(player_data, game_performance_raw):
    """Build a bio dict with summary stats, trophies, and machine highlights."""
    mfp = player_data['mfp_seasons']
    mflp = player_data['mflp_seasons']
    all_seasons = mfp + mflp

    # Trophy counts from completed seasons only
    trophies = {1: 0, 2: 0, 3: 0, 4: 0}
    for s in all_seasons:
        if s.get('status') == 'completed':
            pos = s['summary_stats']['final_position']
            if isinstance(pos, int) and 1 <= pos <= 4:
                trophies[pos] += 1

    total_weeks = sum(s['summary_stats']['weeks_played'] for s in all_seasons)
    total_wins = sum(s['summary_stats']['weekly_wins'] for s in all_seasons)
    total_raw_points = sum(s['summary_stats']['total_raw_points'] for s in all_seasons)

    # Machine highlights: find best win rate with enough games
    best_machine = None
    best_machine_rate = 0
    best_machine_plays = 0
    # Aggregate across all years
    machine_totals = defaultdict(lambda: {'1st': 0, 'total_plays': 0})
    for game_name, years_data in game_performance_raw.items():
        for year_key, stats in years_data.items():
            if isinstance(stats, dict):
                machine_totals[game_name]['1st'] += stats.get('1st', 0)
                machine_totals[game_name]['total_plays'] += stats.get('total_plays', 0)

    for game_name, totals in machine_totals.items():
        if totals['total_plays'] >= MIN_GAMES_FOR_MACHINE_HIGHLIGHT:
            rate = totals['1st'] / totals['total_plays']
            if rate > best_machine_rate:
                best_machine_rate = rate
                best_machine = game_name
                best_machine_plays = totals['total_plays']

    # Build summary sentences
    parts = []
    mfp_completed = [s for s in mfp if s.get('status') == 'completed']
    mflp_completed = [s for s in mflp if s.get('status') == 'completed']
    mfp_active = [s for s in mfp if s.get('status') != 'completed']
    mflp_active = [s for s in mflp if s.get('status') != 'completed']

    league_parts = []
    if mfp_completed:
        league_parts.append(f"{len(mfp_completed)} MFPinball")
    if mflp_completed:
        league_parts.append(f"{len(mflp_completed)} MFLadies Pinball")
    if league_parts:
        parts.append(f"Has played {' and '.join(league_parts)} {'season' if len(all_seasons) == 1 else 'seasons'}")
    active_parts = []
    if mfp_active:
        active_parts.append(f"{len(mfp_active)} MFPinball")
    if mflp_active:
        active_parts.append(f"{len(mflp_active)} MFLadies Pinball")
    if active_parts:
        parts.append(f"Currently playing {' and '.join(active_parts)}")

    if total_weeks > 0:
        parts.append(f"Attended {total_weeks} league nights, winning {total_wins}")

    trophy_parts = []
    if trophies[1] > 0:
        trophy_parts.append(f"{trophies[1]} first place finish{'es' if trophies[1] > 1 else ''}")
    if trophies[2] > 0:
        trophy_parts.append(f"{trophies[2]} second")
    if trophies[3] > 0:
        trophy_parts.append(f"{trophies[3]} third")
    if trophies[4] > 0:
        trophy_parts.append(f"{trophies[4]} fourth")
    if trophy_parts:
        parts.append(f"Finished with {', '.join(trophy_parts)}")

    if best_machine and best_machine_rate >= 0.3:
        parts.append(f"Wins {round(best_machine_rate * 100)}% of the time at {best_machine} ({best_machine_plays} games)")

    return {
        'mfp_seasons_count': len(mfp),
        'mflp_seasons_count': len(mflp),
        'total_weeks': total_weeks,
        'total_wins': total_wins,
        'total_raw_points': total_raw_points,
        'trophies': trophies,
        'best_machine': best_machine,
        'best_machine_rate': best_machine_rate,
        'best_machine_plays': best_machine_plays,
        'summary': '. '.join(parts) + '.' if parts else ''
    }


def generate_player_pages(env, all_series_data):
    """Generates individual player pages and a main players list page."""
    unique_players = {}
    player_categorized_seasons = {}
    all_players_game_performance = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    all_players_game_log = defaultdict(list)
    
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
                    
                    all_players_game_performance[player_id][game_name][year_key]['1st'] += stats['1st']
                    all_players_game_performance[player_id][game_name][year_key]['2nd'] += stats['2nd_4p']
                    all_players_game_performance[player_id][game_name][year_key]['2nd_3p'] += stats['2nd_3p']
                    all_players_game_performance[player_id][game_name][year_key]['3rd'] += stats['3rd_4p']
                    all_players_game_performance[player_id][game_name][year_key]['4th'] += stats['4th_combined']
                    all_players_game_performance[player_id][game_name][year_key]['total_plays'] += stats['total_plays']

        # Populate game log
        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series_data.get('tournamentIds', []))}
        player_name_map = {p['playerId']: p['name'] for p in series_data.get('players', [])}

        for tournament_id_str, games_list in series_data_raw.get('tournament_games_data', {}).items():
            tournament_id = int(tournament_id_str)
            week_num = tournament_id_to_week_num.get(tournament_id, 'N/A')

            for game in games_list:
                arena_name = game.get('arena', {}).get('name', 'Unknown Arena')
                started_at = game.get('startedAt', 'N/A')
                if started_at != 'N/A':
                    started_at = started_at.split('T')[0] # Format YYYY-MM-DD

                # Build per-player info for opponent display
                game_player_info = []
                for idx, pid in enumerate(game['playerIds']):
                    p_points = 'N/A'
                    if 'resultPoints' in game and len(game['resultPoints']) > idx:
                        p_points = game['resultPoints'][idx]
                    p_position = 'N/A'
                    if 'resultPositions' in game:
                        try:
                            p_position = game['resultPositions'].index(pid) + 1
                        except ValueError:
                            pass
                    game_player_info.append({
                        'playerId': pid,
                        'name': player_name_map.get(pid, 'Unknown'),
                        'points': p_points,
                        'position': p_position
                    })

                for p_idx, player_id in enumerate(game['playerIds']):
                    info = game_player_info[p_idx]
                    opponents = [p for p in game_player_info if p['playerId'] != player_id]

                    num_players = len(game['playerIds'])
                    result_str = f"{info['position']}" if info['position'] != 'N/A' else "N/A"

                    all_players_game_log[player_id].append({
                        'date': started_at,
                        'league': league_name_parsed,
                        'season': season_name_parsed,
                        'year': year,
                        'week': week_num,
                        'machine': arena_name,
                        'play_order': p_idx + 1,
                        'result': result_str,
                        'position': info['position'],
                        'players': num_players,
                        'points': info['points'],
                        'opponents': opponents
                    })

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
                'status': series_data.get('status', 'unknown'),
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

        # Sort game log by date descending
        game_log = sorted(all_players_game_log[player_id], key=lambda x: x['date'], reverse=True)

        # Build player bio
        bio = _build_player_bio(data, all_players_game_performance.get(player_id, {}))

        with open(os.path.join(OUTPUT_DIR, f"player_{player_id}.html"), 'w') as f:
            f.write(player_template.render(
                player=player,
                mfp_seasons=data['mfp_seasons'],
                mflp_seasons=data['mflp_seasons'],
                game_performance=data['game_performance'],
                arena_cutoff_date=ARENA_DATA_CUTOFF_DATE.strftime("%B %Y"),
                player_chart_data=player_chart_data,
                all_players_chart_data=all_players_chart_data,
                game_log=game_log,
                bio=bio
            ))
        print(f"Generated player_{player_id}.html")

    players_list_template = env.get_template('players.html')
    with open(os.path.join(OUTPUT_DIR, 'players.html'), 'w') as f:
        f.write(players_list_template.render(players=players_list))
    print("Generated players.html")
    
    return player_categorized_seasons, all_players_chart_data
