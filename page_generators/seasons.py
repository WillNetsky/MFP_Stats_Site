import os
from collections import defaultdict
from data_processor import load_finals_mapping, parse_series_name, apply_year_corrections_to_seasons_list, process_game_data
from api_client import fetch_finals_results, fetch_tournament_games
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
        
        finals_data = {}
        if finals_tournament_ids:
            player_name_map = {p['playerId']: p['name'] for p in series['players']}
            t_ids = finals_tournament_ids if isinstance(finals_tournament_ids, list) else [finals_tournament_ids]

            for i, tid in enumerate(t_ids):
                # If there are multiple tournament IDs, we treat them as concurrent rounds (e.g. Round 1 Group A, Round 1 Group B)
                # UNLESS they are sequential rounds in a bracket.
                # The user request implies that for 8 players, there are two groups of 4 (Round 1), then a final round (Round 2).
                # If 'finals_tournament_ids' is a list [id1, id2], it usually means concurrent tournaments or sequential?
                # In Matchplay, a "finals" might be a single tournament with multiple rounds, OR multiple tournaments.
                # The current mapping structure suggests a list of IDs for a season.
                # If it's a list, we need to know if they are parallel or sequential.
                # Based on the user request: "first two concurrent rounds on the left side, and the finals round on the right side."
                # This suggests we might have multiple tournaments representing the same "logical" round (e.g. Semis Group A, Semis Group B).
                
                # Let's fetch the data first.
                games_data = fetch_tournament_games(tid, series_status=series['status'])

                if games_data and games_data.get('data'):
                    groups = defaultdict(lambda: {'arenas': set(), 'players': defaultdict(lambda: {'name': '', 'games': {}, 'total_points': 0})})
                    tiebreakers = []

                    for game in games_data['data']:
                        arena_name = game.get('arena', {}).get('name', 'Unknown Arena')
                        game_set = game.get('set', 0)
                        
                        if len(game['playerIds']) == 2:
                            tiebreakers.append(game)
                            continue

                        groups[game_set]['arenas'].add(arena_name)

                        for p_idx, player_id in enumerate(game['playerIds']):
                            groups[game_set]['players'][player_id]['name'] = player_name_map.get(player_id, 'Unknown Player')
                            points = float(game['resultPoints'][p_idx])
                            groups[game_set]['players'][player_id]['games'][arena_name] = points
                            groups[game_set]['players'][player_id]['total_points'] += points

                    round_data = {
                        'groups': {f'group_{k}': dict(v) for k, v in groups.items()},
                        'tiebreakers': []
                    }

                    for game in tiebreakers:
                        arena_name = game.get('arena', {}).get('name', 'Unknown Arena')
                        winner_id = game['resultPositions'][0]
                        loser_id = game['resultPositions'][1]
                        round_data['tiebreakers'].append({
                            'winner': player_name_map.get(winner_id, 'Unknown'),
                            'loser': player_name_map.get(loser_id, 'Unknown'),
                            'arena': arena_name
                        })
                    
                    # If we have multiple tournament IDs, we treat them as separate "logical" rounds for now,
                    # but the user wants to group them.
                    # If the list has 2 IDs, and they are concurrent, they should probably be displayed side-by-side or in the same "column".
                    # If they are sequential (Semis -> Finals), they should be separate.
                    # The user says "first two concurrent rounds... and the finals round". This implies 3 entities?
                    # Or maybe "first two concurrent rounds" means 2 groups in ONE tournament (or 2 tournaments) are the "Semis".
                    
                    # Let's assume the list order in finals_mapping reflects the logical flow if they are sequential.
                    # But if they are concurrent (e.g. 2 separate tournaments for 2 groups), we might need to merge them into "Round 1".
                    
                    # Heuristic: If we have multiple IDs, we store them.
                    # The template currently iterates 'round_1', 'round_2'.
                    # If we have [id1, id2], are they Round 1 and Round 2? Or Round 1 Group A and Round 1 Group B?
                    # The user says "if there are 8 players... two groups of 4... top 2 move on".
                    # This sounds like a standard Matchplay finals format where a single tournament has multiple rounds.
                    # BUT, if the mapping has a LIST of IDs, it implies multiple tournaments.
                    
                    # Let's look at Spring 2024: [148304, 148333].
                    # If these are "Semis" and "Finals", they are sequential.
                    # If they are "Group A" and "Group B", they are concurrent.
                    # Usually, Matchplay finals are one tournament with rounds.
                    # If the user split them into two tournaments, we need to know.
                    
                    # However, the code currently assigns `round_{i+1}`. So id1 -> round_1, id2 -> round_2.
                    # If the user wants "first two concurrent rounds on the left", maybe they mean
                    # the first tournament (id1) contains the semi-finals (2 groups), and the second (id2) contains the finals?
                    # OR, maybe id1 and id2 ARE the concurrent rounds?
                    
                    # Let's assume sequential for now (Round 1, Round 2) based on the list index.
                    # If id1 has 2 groups, they will be in `round_1.groups`.
                    # If id2 has 1 group (finals), it will be in `round_2.groups`.
                    
                    # The user says: "As it is now, the finals table is merged with one of the groups from the first round."
                    # This implies that maybe we are merging data incorrectly or the template is displaying them confusingly.
                    # If `finals_data` has `round_1` and `round_2`, the template puts `round_1` in col 1 and `round_2` in col 2.
                    
                    # If the "finals table is merged", maybe we are using the same key for different things?
                    # `groups` dict uses `game_set` (0, 1, 2...) as key.
                    # If a tournament has multiple groups (sets), they are `group_0`, `group_1`.
                    
                    # If the user sees "finals table merged with one of the groups", maybe they mean visually?
                    # Or maybe the data processing is combining them?
                    
                    # Wait, the loop `for i, tid in enumerate(t_ids):` creates `round_{i+1}`.
                    # So if we have 2 IDs, we get `round_1` and `round_2`.
                    # They are distinct in `finals_data`.
                    
                    # If the user says "finals table is merged with one of the groups from the first round",
                    # perhaps they mean that within a SINGLE tournament (id1), there are multiple rounds (Semis and Finals)?
                    # If so, `fetch_tournament_games` returns ALL games.
                    # We group by `set`. In Matchplay, `set` usually distinguishes groups in a round.
                    # But how do we distinguish ROUNDS within a tournament?
                    # Matchplay API `games` usually have a `roundId`.
                    # If a tournament has Semis AND Finals, they will have different `roundId`s.
                    # Our current code ignores `roundId` and groups ONLY by `set`.
                    # THIS IS THE BUG.
                    # If Semis has Set 0 and Set 1, and Finals has Set 0,
                    # `groups[0]` will mix Semis Set 0 and Finals Set 0!
                    
                    # We need to group by `roundId` (or `round` index) AND `set`.
                    # But `roundId` is an opaque ID. We need to know the order.
                    # We can sort games by `startedAt` or `index` to infer rounds, or use `roundId` if we fetch round details.
                    # `fetch_tournament_games` returns games.
                    
                    # Let's refactor to group by `roundId` first.
                    
                    # We need to fetch round details to know the order? Or just sort by `startedAt`?
                    # Games have `startedAt`.
                    # Let's group by `roundId` and sort rounds by the earliest game start time.
                    
                    # New structure:
                    # finals_data = {
                    #   'tournament_1': {
                    #       'rounds': [
                    #           { 'name': 'Round 1', 'groups': { ... } },
                    #           { 'name': 'Round 2', 'groups': { ... } }
                    #       ]
                    #   }
                    # }
                    
                    # But to keep it simple for the template, let's flatten it to logical rounds.
                    # If we have multiple tournaments, we can append their rounds.
                    
                    # Let's change the loop to process games properly.
                    
                    pass # Placeholder to start the refactor block

            # Refactored logic for processing finals data
            all_finals_rounds = []
            
            t_ids = finals_tournament_ids if isinstance(finals_tournament_ids, list) else [finals_tournament_ids]
            
            for tid in t_ids:
                games_data = fetch_tournament_games(tid, series_status=series['status'])
                if not games_data or not games_data.get('data'):
                    continue
                
                # Group games by roundId
                games_by_round = defaultdict(list)
                round_start_times = {}
                
                for game in games_data['data']:
                    rid = game['roundId']
                    games_by_round[rid].append(game)
                    
                    # Track start time to sort rounds
                    started_at = game.get('startedAt')
                    if started_at:
                        if rid not in round_start_times or started_at < round_start_times[rid]:
                            round_start_times[rid] = started_at
                    elif rid not in round_start_times:
                         # Fallback if no start time (unlikely for completed games), use 0 or max
                         round_start_times[rid] = "9999-99-99"

                # Sort rounds by start time
                sorted_round_ids = sorted(games_by_round.keys(), key=lambda r: round_start_times.get(r, "9999"))
                
                for rid in sorted_round_ids:
                    round_games = games_by_round[rid]
                    
                    groups = defaultdict(lambda: {'arenas': set(), 'players': defaultdict(lambda: {'name': '', 'games': {}, 'total_points': 0})})
                    tiebreakers = []
                    
                    for game in round_games:
                        arena_name = game.get('arena', {}).get('name', 'Unknown Arena')
                        game_set = game.get('set', 0)
                        
                        # Tiebreakers usually have 2 players (or fewer than group size), but standard groups can be 3 or 4.
                        # A better heuristic for tiebreakers might be needed, or just display them as groups.
                        # For now, let's keep the 2-player check but be careful. 
                        # Actually, head-to-head finals are 2 players.
                        # If it's a tiebreaker, it usually has a specific flag or is a separate round?
                        # Let's assume standard group play for now.
                        # If it's a tiebreaker round, it often has fewer games/players.
                        
                        # Let's treat everything as a group for now to avoid hiding data.
                        # If we want to separate tiebreakers, we can check if it's a "tiebreaker" round type if API provided it, but we only have games.
                        
                        groups[game_set]['arenas'].add(arena_name)
                        for p_idx, player_id in enumerate(game['playerIds']):
                            groups[game_set]['players'][player_id]['name'] = player_name_map.get(player_id, 'Unknown Player')
                            if p_idx < len(game['resultPoints']):
                                points = float(game['resultPoints'][p_idx])
                                groups[game_set]['players'][player_id]['games'][arena_name] = points
                                groups[game_set]['players'][player_id]['total_points'] += points
                    
                    all_finals_rounds.append({
                        'groups': {f'group_{k}': dict(v) for k, v in groups.items()},
                        'tiebreakers': tiebreakers # Empty for now as we treat all as groups
                    })

            # Now we have a list of rounds.
            # We want to display "first two concurrent rounds on the left side, and the finals round on the right side."
            # This implies we expect 2 logical phases: Semis and Finals.
            # If `all_finals_rounds` has 2 entries (Round 1, Round 2), we map them.
            # If it has 1 entry (e.g. just Finals), we map it.
            
            # Let's structure `finals_data` for the template.
            # We'll pass the list of rounds.
            finals_data['rounds'] = all_finals_rounds

        tournament_id_to_week_num = {tid: i + 1 for i, tid in enumerate(series['tournamentIds'])}
        
        season_players_data = []
        
        for player_info in series['players']:
            player_id = player_info['playerId']
            
            # For active seasons, standings might not be fully populated or reliable for 'position'
            # if no games have been played, but if 1 week is done, they should be there.
            # However, if a player hasn't played yet, they might not be in standings or have position 0/null.
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

            # Only include players who have played at least one week OR if the season hasn't started but they are registered
            # Actually, for the stats table, we probably want to see everyone registered, 
            # but if they haven't played, their stats will be 0.
            # The issue might be that for an active season with 1 week, 
            # if 'standings' is empty or not updated by Matchplay yet, we might miss data if we rely solely on it.
            # But we are iterating over series['players'], so we should get everyone.
            
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
        
        # Sort by qualifying position. If N/A (not played/ranked), put at end.
        # For active seasons, position might be dynamic.
        season_players_data.sort(key=lambda x: (
            x['qualifying_position'] if isinstance(x['qualifying_position'], int) else float('inf'),
            -x['total_raw_points'] # Tie-break with raw points
        ))

        with open(os.path.join(OUTPUT_DIR, f"season_{series_id}.html"), 'w') as f:
            f.write(template.render(
                season=series,
                season_players_data=season_players_data,
                players=series['players'],
                has_finals=has_finals,
                finals_data=finals_data
            ))
        print(f"Generated season_{series_id}.html")
