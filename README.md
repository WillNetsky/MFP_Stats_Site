# Matchplay Pinball League Stats Site Generator

This project generates a static website to display statistics for pinball leagues managed through Matchplay Events. It fetches data from the Matchplay API, processes it, and renders dynamic HTML pages with season overviews, player statistics, and various leaderboards.

## Features

*   **Automated Data Fetching:** Pulls the latest league data from the Matchplay API.
*   **Static Site Generation:** Creates a fast, deployable static HTML website.
*   **Season Overviews:** Displays detailed information for each league season, including top finishers.
*   **Player Profiles:** Dedicated pages for each player with their season-by-season performance.
*   **Leaderboards:** All-time leaderboards for various metrics (e.g., total points, weekly wins, most improved player).
*   **Responsive Design:** Tables are designed to scroll horizontally on smaller screens for better mobile experience.
*   **Dark Mode Toggle:** Users can switch between light, dark, and auto themes.
*   **Search & Filtering:** Easily find players and filter seasons by year.
*   **Automated Deployment:** Configured for Continuous Deployment via GitHub Actions to GitHub Pages.

## Technologies Used

*   **Python:** Core scripting language.
*   **Jinja2:** Templating engine for HTML generation.
*   **requests:** For interacting with the Matchplay API.
*   **python-dotenv:** For managing environment variables (API keys).
*   **argparse:** For command-line argument parsing.
*   **Pico.css:** A minimalist CSS framework for styling.
*   **GitHub Actions:** For CI/CD automation.
*   **GitHub Pages:** For static site hosting.

## Project Structure

The project is organized into modular Python scripts:

*   `main.py`: The main entry point for running data fetching and site generation.
*   `api_client.py`: Handles all interactions with the Matchplay Events API.
*   `data_processor.py`: Contains logic for loading, parsing, and transforming raw data.
*   `site_generator.py`: Responsible for rendering Jinja2 templates and writing HTML files to the `output` directory.
*   `config.py`: Centralized configuration settings for the project (e.g., excluded series, directory paths).
*   `requirements.txt`: Lists all Python dependencies.
*   `matchplay-openapi.yaml`: OpenAPI specification for the Matchplay API.
*   `templates/`: Contains Jinja2 HTML templates (`.html` files).
*   `static/`: Contains static assets like CSS files.
*   `data/`: Stores cached API responses and mapping files (e.g., `finals_mapping.json`).
*   `.github/workflows/deploy.yml`: GitHub Actions workflow definition for automated deployment.
*   `player_page_example_files/`: Example files for player pages (if applicable, otherwise consider removing or clarifying).

## Customization

*   **Excluded Series:** Modify the `EXCLUDED_SERIES_NAMES` list in `config.py` to control which series are included or excluded from the generated statistics.
*   **Templates:** The HTML structure and content can be customized by editing the Jinja2 templates located in the `templates/` directory.
*   **Static Assets:** Update CSS styles or add new static files in the `static/` directory.

## Future Enhancements

*   **Head-to-Head Statistics:** Develop a feature to compare two players' historical performance against each other.
*   **Advanced Filtering:** Add more sophisticated filtering options for seasons and players.
*   **Improved Mobile Table Display:** Further optimize table presentation for very small screens.
