"""
Glicko-1 rating calculation for league players.

Each 3- or 4-player group game is decomposed into all pairwise (1v1) matchups.
The player who finished higher wins each matchup. All matchups from a single game
are processed simultaneously using pre-game ratings/RDs (snapshot approach).

Glicko-1 adds a Ratings Deviation (RD) per player:
  - New players start at RD = 350 (maximum uncertainty).
  - RD shrinks as games are played, reflecting growing confidence in the rating.
  - RD can increase over time for inactive players (not implemented here since
    the league has regular seasons and activity is roughly continuous).

Reference: http://www.glicko.net/glicko/glicko.pdf
"""

import math
from data_processor import parse_series_name

DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
Q = math.log(10) / 400.0


def _g(rd):
    """Reduces the impact of an opponent based on their RD."""
    return 1.0 / math.sqrt(1.0 + 3.0 * Q**2 * rd**2 / math.pi**2)


def _E(r, r_j, rd_j):
    """Expected score for player with rating r against opponent (r_j, rd_j)."""
    return 1.0 / (1.0 + 10.0 ** (-_g(rd_j) * (r - r_j) / 400.0))


def _glicko_update(r, rd, opponents):
    """
    Update a player's rating and RD given a list of pairwise outcomes.

    opponents: list of (r_j, rd_j, score) where score=1.0 (win) or 0.0 (loss)

    Returns (new_rating, new_rd).
    """
    if not opponents:
        return r, rd

    d_sq_inv = Q**2 * sum(
        _g(rd_j)**2 * _E(r, r_j, rd_j) * (1.0 - _E(r, r_j, rd_j))
        for r_j, rd_j, _ in opponents
    )
    d_sq = 1.0 / d_sq_inv if d_sq_inv else float('inf')

    r_delta = (Q / (1.0 / rd**2 + 1.0 / d_sq)) * sum(
        _g(rd_j) * (s - _E(r, r_j, rd_j))
        for r_j, rd_j, s in opponents
    )

    new_r = r + r_delta
    new_rd = math.sqrt(1.0 / (1.0 / rd**2 + 1.0 / d_sq))
    return new_r, new_rd


def calculate_elo_ratings(all_series_data):
    """
    Calculate Glicko-1 ratings for all players, separately per league.

    Games are processed in chronological order (by startedAt timestamp).
    Only MFPinball and MFLadies Pinball series are included.

    Returns:
        dict with keys 'mfp' and 'mflp', each mapping player_id to:
            {playerId, name, rating, rd, peak, games, history: [{date, rating, rd}]}
    """
    all_games = []

    for series_data_raw in all_series_data:
        series = series_data_raw['data']
        series_name = series['name']
        _, _, league_name = parse_series_name(series_name)

        if league_name not in ('MFPinball', 'MFLadies Pinball'):
            continue

        player_name_map = {p['playerId']: p['name'] for p in series.get('players', [])}

        for games_list in series_data_raw.get('tournament_games_data', {}).values():
            for game in games_list:
                if game.get('bye'):
                    continue
                result_positions = game.get('resultPositions')
                if not result_positions or len(result_positions) < 2:
                    continue
                if not game.get('playerIds') or len(game['playerIds']) < 2:
                    continue

                all_games.append({
                    'league': league_name,
                    'started_at': game.get('startedAt', ''),
                    'result_positions': result_positions,
                    'player_name_map': player_name_map,
                })

    all_games.sort(key=lambda g: g['started_at'])

    mfp_ratings = {}
    mflp_ratings = {}

    def _get_player(ratings, player_id, name):
        if player_id not in ratings:
            ratings[player_id] = {
                'playerId': player_id,
                'name': name or '',
                'rating': DEFAULT_RATING,
                'rd': DEFAULT_RD,
                'peak': DEFAULT_RATING,
                'games': 0,
                'history': [],
            }
        elif name:
            ratings[player_id]['name'] = name
        return ratings[player_id]

    for game in all_games:
        ratings = mfp_ratings if game['league'] == 'MFPinball' else mflp_ratings
        result_positions = game['result_positions']
        player_name_map = game['player_name_map']
        n = len(result_positions)

        # Snapshot pre-game ratings/RDs for all players
        for player_id in result_positions:
            _get_player(ratings, player_id, player_name_map.get(player_id, ''))

        snapshot = {pid: (ratings[pid]['rating'], ratings[pid]['rd']) for pid in result_positions}

        # Build opponent lists for each player from all pairwise matchups
        # result_positions is ordered 1st → last, so position index = finish order
        finish_rank = {pid: i for i, pid in enumerate(result_positions)}
        opponents_for = {pid: [] for pid in result_positions}

        for i in range(n):
            for j in range(i + 1, n):
                winner_id = result_positions[i]
                loser_id = result_positions[j]
                r_w, rd_w = snapshot[winner_id]
                r_l, rd_l = snapshot[loser_id]
                opponents_for[winner_id].append((r_l, rd_l, 1.0))
                opponents_for[loser_id].append((r_w, rd_w, 0.0))

        # Apply Glicko-1 update for each player
        date_str = game['started_at'][:10] if game['started_at'] else ''
        for player_id in result_positions:
            p = ratings[player_id]
            r_old, rd_old = snapshot[player_id]
            new_r, new_rd = _glicko_update(r_old, rd_old, opponents_for[player_id])
            p['rating'] = new_r
            p['rd'] = new_rd
            p['games'] += 1
            if new_r > p['peak']:
                p['peak'] = new_r
            p['history'].append({
                'date': date_str,
                'rating': round(new_r, 1),
                'rd': round(new_rd, 1),
            })

    return {'mfp': mfp_ratings, 'mflp': mflp_ratings}
