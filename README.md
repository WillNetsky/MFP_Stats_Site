# Matchplay Pinball League Stats Site Generator

This project generates a static website to display statistics for pinball leagues managed through Matchplay Events. It fetches data from the Matchplay API, processes it, and renders HTML pages with season overviews, player statistics, leaderboards, charts, and frivolities.

## Overarching Ideas
* This site is meant to be like baseballreference.com for the competitive pinball sanctioned by MFPinball.org
* Each league (MFPinball and MFLadies) are separate but entirely equal and must always be treated as such on every page 
* Player pages should show the full extent of what players have done in the leagues and be similar to what you would see on the back of a baseball card
* Season pages should try to describe the results of the season as best as possible
* Leaderboards page is for comparing the best players
* Frivolities page is similar to the leaderboards page, but for finding statistical oddities
* Charts page is for everything else

## Features

*   **Automated Data Fetching:** Pulls league data from the Matchplay API with 24-hour cache expiry.
*   **Static Site Generation:** Creates a deployable static HTML website.
*   **Season Overviews:** Detailed information for each league season, including standings, top finishers, and finals results. Separate tracking for MFPinball and MFLadies leagues.
*   **Player Profiles:** Dedicated pages for each player with season-by-season performance, game logs, machine win rates, and Chart.js visualizations. Active seasons are highlighted with a glowing border.
*   **Leaderboards:** All-time leaderboards for total points, weekly wins, perfect nights, most improved player, and more.
*   **Charts:** Chart.js visualizations of player trends and league data.
*   **Frivolities:** Fun stats including perfect nights (35 points), almost perfect nights (34), wooden nickels (5), biggest week-to-week drops, tournaments on this day, and one-hit wonders.
*   **Score Color-Coding:** Dynamic gradient from red (5) through white (20) to green (34) and gold (35).
*   **Sortable Tables:** Click column headers to sort any data table.
*   **Responsive Design:** Tables scroll horizontally on smaller screens.
*   **Dark Mode Toggle:** Switch between light, dark, and auto themes.
*   **Search & Filtering:** Find players and filter seasons by year.
*   **Automated Deployment:** Continuous deployment via GitHub Actions to GitHub Pages, with daily scheduled builds.

## Technologies Used

*   **Python:** Core scripting language.
*   **Jinja2:** Templating engine for HTML generation.
*   **requests:** For interacting with the Matchplay API.
*   **pandas:** Data manipulation and analysis.
*   **python-dotenv:** For managing environment variables (API keys).
*   **argparse:** For command-line argument parsing.
*   **Pico.css:** A minimalist CSS framework for styling (loaded via CDN).
*   **Chart.js:** JavaScript charting library for player and league visualizations (loaded via CDN).
*   **GitHub Actions:** For CI/CD automation.
*   **GitHub Pages:** For static site hosting.

## Project Structure

```
├── main.py                  # Entry point: --fetch and/or --generate
├── api_client.py            # Matchplay API interactions with caching
├── api_explorer.py          # Utility for exploring API endpoints (development)
├── data_processor.py        # Data loading, parsing, and transformation
├── site_generator.py        # Orchestrates page generation and static asset copying
├── config.py                # Centralized configuration (excluded series, paths, thresholds)
├── page_generators/         # Modular page generation
│   ├── caching.py           # Memoization decorator for API calls
│   ├── charts.py            # Charts page generation
│   ├── frivolities.py       # Fun stats page generation
│   ├── helpers.py           # Jinja2 filters (score colors, number formatting)
│   ├── leaderboards.py      # Leaderboard calculations and page generation
│   ├── players.py           # Individual player page generation
│   └── seasons.py           # Season list and individual season page generation
├── templates/               # Jinja2 HTML templates
│   ├── base.html            # Base layout with nav, scripts, and score coloring
│   ├── _navbar.html         # Navigation component
│   ├── index.html           # Home page
│   ├── seasons.html         # Season list with year filters
│   ├── season.html          # Individual season detail
│   ├── players.html         # Player list with search
│   ├── player.html          # Individual player profile
│   ├── charts.html          # Chart.js visualizations
│   ├── leaderboards.html    # Leaderboard container
│   ├── leaderboard_tables.html  # Leaderboard table components
│   └── frivolities.html     # Fun stats and sortable tables
├── static/
│   └── style.css            # Custom styles (Pico.css overrides, trophy colors, score badges)
├── data/                    # Cached API responses (series, tournaments, games, finals, arenas)
├── output/                  # Generated static site (gitignored)
├── player_page_example_files/   # Baseball Reference examples used as design inspiration
├── .github/workflows/
│   └── deploy.yml           # CI/CD: fetch, generate, deploy to gh-pages
├── requirements.txt         # Python dependencies
├── matchplay-openapi.yaml   # Matchplay API OpenAPI specification
└── .env                     # API key and user ID (gitignored)
```

## Setup

1.  Clone the repository.
2.  Create a Python virtual environment and install dependencies:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  Create a `.env` file in the project root with your Matchplay API credentials:
    ```
    MATCHPLAY_API_KEY = "your_api_key_here"
    USER_ID = "your_user_id_here"
    ```

## Usage

```bash
# Fetch latest data from the API and generate the site
python main.py --fetch --generate

# Fetch data only (updates cached JSON in data/)
python main.py --fetch

# Generate site only (uses cached data, default if no flags given)
python main.py --generate
python main.py
```

The generated site is written to the `output/` directory.

## Customization

*   **Excluded Series:** Modify the `EXCLUDED_SERIES_NAMES` list in `config.py` to control which series are included or excluded from processing.
*   **League Names:** Update `MFLADIES_LEAGUE_NAMES` in `config.py` to recognize additional name variations for the MFLadies league.
*   **Leaderboard Thresholds:** Adjust `MIN_WEEKS_FOR_IMPROVEMENT` in `config.py` to change the minimum weeks required for the Most Improved Player leaderboard.
*   **Cache Duration:** Change `CACHE_EXPIRY_HOURS` in `config.py` to control how long fetched API data is considered fresh.
*   **Templates:** Edit the Jinja2 templates in `templates/` to change the HTML structure and content.
*   **Static Assets:** Update CSS styles or add new static files in `static/`.

## TODO

* Site-wide
  * Tournaments - Add all of the league adjacent tournaments from Cary's organizer ID, requires filtering relevant tournaments
  * Light and dark theme (one that holds between pages and plays well with the flair)
  * Use the <details> tag more universally
  * Better display in portrait on web
* Seasons
  * Portrait sized windows of seasons with finals overlay the semi-finals and finals columns
  * <details> tag on each league type
  * Racing horizontal bar chart
  * toggle between week # scores and nth best scores on season page
  * IFPA wpprs given to winner (likely need to manually document this, or document the ifpa ids)
  * Chart of number of players with WPPRS overlayed (possible one-off? scatter of qualified players vs wpprs to the winner?)
* Players
  * players.html - we need to fix this, a list of all links to players is useless, maybe change to a table of all players basic stats
  * Bio section - ifpa# links to ifpa page (simple url manipulation)
  * Bio section - get everybody's initials (manual, historical)
  * Bio section - brief summary "player has played x seasons of MFP, x of MFLP, won X times, won X weeks etc" sorta generative
      include things like "They win at Dolly Parton 75% of the time" limit by qualifying games/weeks, otherwise "they have played x weeks", include something for every player
  * Bio section - trophies won (they link to where they were won if not list all as achievements)
  * Bio section - OG office flair (players who played at seasons/tournaments that took place at The Office)
  * Add opponents to game log table (p1 name x pts, etc)
* Charts
  * BUG: "Statistic:" is on a separate line from it's dropdown, unlike "Select Player:" and "Compare With:"
  * As many stats as possible
  * Big ass scatter plots with all available data
* Leaderboards
  * Paginate all time leaders, unecessary if players.html becomes the sortable version of all players as a table
  * Top Season Performances - probably include more players, with pagination probably not a big deal to include all
  * use <details> tag for each individual table within each league type
* Frivolities
  * use <details> tag for each individual table within each league type
  * "The Players Formally Known As" players with only a first name (may be better to add as a player page flair)
  
* Constants to research and document (should separate historian role vs scorekeeper)
  * ~~when arena data becomes trustworthy~~ — Season id 748 (Fall 18) is the first season with correct arena data
  * strikes IFPA start date
  * when Bee took over strikes (this is when strikes begins to count, similar but different to the IFPA start date)
  * date of transition from The Office to Lynn's Arcade
* Future Ideas
  * Pages for each week, possibly when we add the tournaments since they're also individual tournaments in matchplay
  * Integration with Twitch vods(starting with the winter 2026 season)
  * Pages for each arena, with every game played and players (eventually integrate with player bio section (player is #1 all time at dolly parton))
  * separate pages for years? I dont think anyone cares about this particuilar split, but yearly statistics are probably useful
  * more flair images (wooden nickel, perfect night etc)
  * images for every trophy design