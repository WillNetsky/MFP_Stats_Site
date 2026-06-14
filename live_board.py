#!/usr/bin/env python3
"""
MFP Live Board server.
Run: python live_board.py
Then open: http://localhost:5252
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MATCHPLAY_API_KEY")
USER_ID = os.getenv("USER_ID")
BASE_URL = "https://app.matchplay.events/api"
PORT = 5252

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def api_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_live_data():
    # Find all active tournaments owned by user
    tournaments = api_get("/tournaments", {"owner": USER_ID, "status": "started"}).get("data", [])
    if not tournaments:
        return {"active": False}

    all_games    = []
    all_standings = []
    tournament_names = []
    master_player_map = {}

    for t in tournaments:
        tournament_id   = t.get("tournamentId") or t.get("id")
        tournament_name = t.get("name", "Tournament")
        tournament_names.append(tournament_name)

        # Tournament details — players and arenas
        details   = api_get(f"/tournaments/{tournament_id}", {"includeArenas": "true", "includePlayers": "true"}).get("data", {})
        player_map = {p["playerId"]: p["name"] for p in details.get("players", [])}
        arena_map  = {a["arenaId"]: a["name"]  for a in details.get("arenas", [])}
        master_player_map.update(player_map)

        # Games from the active/latest round
        games_data = api_get(f"/tournaments/{tournament_id}/games", {"round": "activeOrLatest"}).get("data", [])

        for game in games_data:
            result_map = {}
            positions = game.get("resultPositions") or []
            points    = game.get("resultPoints") or []
            for pid, pts in zip(positions, points):
                if pid is not None:
                    result_map[pid] = pts

            arena_id   = game.get("arenaId")
            arena_name = arena_map.get(arena_id) or (game.get("arena") or {}).get("name") or "TBD"

            all_games.append({
                "gameId":      game.get("gameId"),
                "arena":       arena_name,
                "tournament":  tournament_name,
                "status":      game.get("status"),
                "players": [
                    {"id": pid, "name": player_map.get(pid, f"Player {pid}")}
                    for pid in (game.get("playerIds") or [])
                ],
                "resultMap": {str(k): v for k, v in result_map.items()},
            })

        # Standings — use the first tournament that has them
        if not all_standings:
            standings_raw = api_get(f"/tournaments/{tournament_id}/standings")
            if isinstance(standings_raw, dict):
                standings_raw = standings_raw.get("data", [])
            if standings_raw:
                all_standings = [
                    {
                        "position": s.get("position"),
                        "name":     player_map.get(s.get("playerId"), f"Player {s.get('playerId')}"),
                        "points":   s.get("points"),
                    }
                    for s in standings_raw
                ]

    # Sort games: live first, then queued, then completed
    status_order = {"started": 0, "planned": 1, "completed": 2}
    all_games.sort(key=lambda g: status_order.get(g["status"], 1))

    return {
        "active":          True,
        "tournamentName":  " / ".join(tournament_names),
        "games":           all_games,
        "standings":       all_standings,
    }


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MFP Live Board</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #08080f;
    color: #ddd;
    font-family: 'Segoe UI', system-ui, sans-serif;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

#header {
    background: #111118;
    padding: 0.6rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 2px solid #1e1e30;
    flex-shrink: 0;
}
#header h1 { font-size: 1.6rem; color: #fff; letter-spacing: 0.02em; }
#header .meta { font-size: 0.85rem; color: #555; }

#main {
    display: flex;
    flex: 1;
    overflow: hidden;
}

/* ── Games ── */
#games-section {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
}
#section-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #555;
    margin-bottom: 0.75rem;
}
#games-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.65rem;
}

.game-card {
    background: #111120;
    border: 1px solid #202030;
    border-radius: 8px;
    padding: 0.7rem 0.85rem;
}
.game-card.live {
    border-color: #3a8a55;
    box-shadow: 0 0 14px rgba(50,160,90,0.18);
}
.game-card .machine {
    font-size: 1rem;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 0.35rem;
}
.badge {
    display: inline-block;
    font-size: 0.65rem;
    padding: 0.1rem 0.45rem;
    border-radius: 99px;
    margin-bottom: 0.4rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge.live   { background: rgba(50,160,90,0.15); color: #3a8; border: 1px solid #3a8; }
.badge.done   { background: rgba(80,80,80,0.15);  color: #555; border: 1px solid #333; }
.badge.queued { background: rgba(80,80,160,0.15); color: #77a; border: 1px solid #446; }

.player-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.2rem 0;
    font-size: 0.9rem;
}
.player-row .slot {
    width: 1.3rem;
    height: 1.3rem;
    border-radius: 50%;
    background: #1c1c2c;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65rem;
    font-weight: 700;
    color: #666;
    flex-shrink: 0;
}
.player-row.finished .slot { background: #2a5a3a; color: #3a8; }
.player-row .pname {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.player-row .pts {
    font-size: 0.8rem;
    color: #3a8;
    font-weight: 700;
    flex-shrink: 0;
}

/* ── Standings ── */
#standings-section {
    width: 280px;
    background: #0c0c18;
    border-left: 2px solid #1e1e30;
    padding: 1rem;
    overflow-y: auto;
    flex-shrink: 0;
}
#standings-section h2 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #555;
    margin-bottom: 0.75rem;
}
.s-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.5rem;
    border-radius: 5px;
    font-size: 0.9rem;
}
.s-row:nth-child(odd) { background: #111120; }
.s-row .pos {
    width: 1.8rem;
    text-align: right;
    font-weight: 700;
    color: #555;
    flex-shrink: 0;
}
.s-row.gold   .pos { color: #d4a000; }
.s-row.silver .pos { color: #999; }
.s-row.bronze .pos { color: #a06030; }
.s-row .sname {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.s-row .spts {
    color: #888;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
}

#no-tournament {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    color: #333;
}
</style>
</head>
<body>
<div id="header">
    <h1 id="t-name">MFP Live Board</h1>
    <span class="meta" id="updated">Loading…</span>
</div>
<div id="main">
    <div id="no-tournament">No active tournament</div>
    <div id="games-section" style="display:none">
        <div id="section-label">Current Round</div>
        <div id="games-grid"></div>
    </div>
    <div id="standings-section" style="display:none">
        <h2>Standings</h2>
        <div id="standings-list"></div>
    </div>
</div>

<script>
async function refresh() {
    try {
        const resp = await fetch('/api/live');
        const data = await resp.json();
        render(data);
        document.getElementById('updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
    } catch (e) {
        document.getElementById('updated').textContent = 'Error — retrying…';
    }
}

function render(data) {
    const noT = document.getElementById('no-tournament');
    const gs  = document.getElementById('games-section');
    const ss  = document.getElementById('standings-section');

    if (!data.active) {
        noT.style.display = 'flex';
        gs.style.display  = 'none';
        ss.style.display  = 'none';
        return;
    }

    noT.style.display = 'none';
    gs.style.display  = '';
    ss.style.display  = '';
    document.getElementById('t-name').textContent = data.tournamentName;

    // Games
    const grid = document.getElementById('games-grid');
    grid.innerHTML = '';
    for (const game of data.games) {
        const live      = game.status === 'started';
        const completed = game.status === 'completed';
        const badgeCls  = live ? 'live' : completed ? 'done' : 'queued';
        const badgeTxt  = live ? '● Live' : completed ? 'Done' : 'Queued';

        const playersHtml = game.players.map((p, i) => {
            const pts      = game.resultMap[String(p.id)];
            const finished = pts !== undefined;
            return `<div class="player-row ${finished ? 'finished' : ''}">
                <span class="slot">${i + 1}</span>
                <span class="pname">${p.name}</span>
                ${finished ? `<span class="pts">${parseFloat(pts).toFixed(0)}pts</span>` : ''}
            </div>`;
        }).join('');

        const card = document.createElement('div');
        card.className = 'game-card' + (live ? ' live' : '');
        card.innerHTML = `
            <div class="machine">${game.arena}</div>
            <span class="badge ${badgeCls}">${badgeTxt}</span>
            ${playersHtml}`;
        grid.appendChild(card);
    }

    // Standings
    const list = document.getElementById('standings-list');
    list.innerHTML = '';
    for (const s of data.standings) {
        const cls = s.position === 1 ? 'gold' : s.position === 2 ? 'silver' : s.position === 3 ? 'bronze' : '';
        const row = document.createElement('div');
        row.className = `s-row ${cls}`;
        row.innerHTML = `
            <span class="pos">${s.position}</span>
            <span class="sname">${s.name}</span>
            <span class="spts">${parseFloat(s.points).toFixed(1)}</span>`;
        list.appendChild(row);
    }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress per-request noise

    def do_GET(self):
        if self.path == '/':
            body = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == '/api/live':
            try:
                data = get_live_data()
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    server = ThreadedHTTPServer(('', PORT), Handler)
    print(f"Live board: http://localhost:{PORT}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
