import os
from collections import defaultdict
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, process_game_data
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
            'year': year,
            'season_name': season_name_parsed,
            'league_name': league_name_parsed,
            'status': series['status'],
            'has_finals': "No",
            'first_place_player': None,
            'second_place_player': None,
            'third_place_player': None,
            'fourth_place_player': None,
            'qualified_players_count': 0,
            'qualification_threshold': 0
        }

        if "MFPinball" in league_name_parsed or "MFP" in league_name_parsed:
            mfp_seasons_raw.append(season_entry)
        elif "Monterey Flipper Ladies Pinball" in league_name_parsed or "MFLadies" in league_name_parsed:
            mflp_seasons_raw.append(season_entry)
    
    mfp_seasons = apply_year_corrections_to_seasons_list(mfp_seasons_raw)
    mflp_seasons = apply_year_corrections_to_seasons_list(mflp_seasons_raw)

    for season_list in [mfp_seasons, mflp_seasons]:
        for season_entry in season_list:
            league_name = season_entry['league_name']
            year = season_entry['year']
            season_name = season_entry['season_name']
            series_id = season_entry['seriesId']
            all_years.add(year)

            finals_tournament_ids = None
            if league_name in finals_mapping and year != "N/A" and season_name != "N/A":
                key = f"{season_name} {year}"
                finals_tournament_ids = finals_mapping[league_name].get(key)
            
            season_entry['has_finals'] = "Yes" if finals_tournament_ids else "No"
            
            original_series_data_for_top4 = series_data_map.get(series_id)
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
                        top_players_standings.sort(key=lambda x: x['position'])
                    else:
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
            'original_series_data': series_data_raw
        })
    
    processed_seasons_for_pages = apply_year_corrections_to_seasons_list(processed_seasons_for_pages)
    
    for season_entry in processed_seasons_for_pages:
        series_id = season_entry['seriesId']
        series = season_entry['original_series_data']['data']
        game_data = process_game_data(season_entry['original_series_data'])

        finals_tournament_ids = None
        if season_entry['league_name'] in finals_mapping and season_entry['year'] != "N/A" and season_entry['season_name'] != "N/A":
            key = f"{season_entry['season_name']} {season_entry['year']}"
            finals_tournament_ids = finals_mapping[season_entry['league_name']].get(key)
        
        has_finals = "Yes" if finals_tournament_ids else "No"
        
        finals_results = None
        if finals_tournament_ids:
            raw_finals_standings = fetch_finals_results(finals_tournament_ids)
            if raw_finals_standings:
                player_name_map_for_finals = {p['playerId']: p['name'] for p in series['players']}
                finals_results = []
                for result in raw_finals_standings:
                    finals_results.append({
                        'position': result['position'],
                        'playerId': result['playerId'],
                        'name': player_name_map_for_finals.get(result['playerId'], 'Unknown Player')
                    })
                finals_results.sort(key=lambda x: x['position'])

        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series['tournamentIds'])}
        
        season_players_data = []
        
        for player_info in series['players']:
            player_id = player_info['playerId']
            
            player_standing = next((s for s in series['standings'] if s['playerId'] == player_id), None)
            
            qualifying_position = player_standing['position'] if player_standing else 'N/A'
            total_adjusted_points = player_standing['pointsAdjusted'] if player_standing else 0.0
            
            weekly_scores_raw = []
            total_raw_points = 0.0
            
            if 'tournamentPoints' in series and series['tournamentPoints']:
                for tournament_id_str, player_points_map in series['tournamentPoints'].items():
                    if str(player_id) in player_points_map:
                        points = float(series['tournamentPoints'][tournament_id_str][str(player_id)])
                        weekly_scores_raw.append({'tournament_id': int(tournament_id_str), 'points': points})
                        total_raw_points += points
            
            weekly_scores_raw.sort(key=lambda x: x['tournament_id'])

            weekly_scores_ordered = ['N/A'] * 10 
            num_weeks_played_by_player = 0
            for score_entry in weekly_scores_raw:
                week_num = tournament_id_to_week_num.get(score_entry['tournament_id'])
                if week_num is not None and 1 <= week_num <= 10:
                    weekly_scores_ordered[week_num - 1] = score_entry['points']
                    num_weeks_played_by_player += 1
            
            average_points_per_week = total_raw_points / num_weeks_played_by_player if num_weeks_played_by_player > 0 else 0.0

            player_game_stats = game_data['by_player'].get(player_id, defaultdict(int))

            season_players_data.append({
                'playerId': player_id,
                'name': player_info['name'],
                'qualifying_position': qualifying_position,
                'total_adjusted_points': total_adjusted_points,
                'total_raw_points': round(total_raw_points, 2),
                'average_points_per_week': round(average_points_per_week, 2),
                'weekly_scores': weekly_scores_ordered,
                'game_outcomes': player_game_stats
            })
        
        season_players_data.sort(key=lambda x: x['qualifying_position'] if isinstance(x['qualifying_position'], int) else float('inf'))

        with open(os.path.join(OUTPUT_DIR, f"season_{series_id}.html"), 'w') as f:
            f.write(template.render(
                season=series,
                season_players_data=season_players_data,
                players=series['players'],
                has_finals=has_finals,
                finals_tournament_ids=finals_tournament_ids,
                finals_results=finals_results
            ))
        print(f"Generated season_{series_id}.html")
