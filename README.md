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

## Quick Start

Follow these steps to get the site up and running locally:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/WillNetsky/MFP_Stats_Site.git
    cd MFP_Stats_Site
    ```

2.  **Set up Python environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `.\venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Configure API Keys:**
    Create a `.env` file in the root directory with your Matchplay API Key and your Matchplay User ID:
    ```
    MATCHPLAY_API_KEY="YOUR_MATCHPLAY_API_KEY"
    USER_ID="YOUR_MATCHPLAY_USER_ID" # Your Matchplay Events User ID
    ```
    Replace `"YOUR_MATCHPLAY_API_KEY"` and `"YOUR_MATCHPLAY_USER_ID"` with your actual credentials.

4.  **Fetch data and generate the site:**
    ```bash
    python main.py --fetch --generate
    ```
    After generation, open `output/index.html` in your browser to view the site.

## Setup (Local Development)

To set up the project locally (detailed version):

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/WillNetsky/MFP_Stats_Site.git
    cd MFP_Stats_Site
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows:
    # .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Keys:**
    Create a `.env` file in the root directory of the project with your Matchplay API Key and User ID:
    ```
    MATCHPLAY_API_KEY="YOUR_MATCHPLAY_API_KEY"
    USER_ID="YOUR_MATCHPLAY_USER_ID" # Your Matchplay Events User ID
    ```
    Replace `"YOUR_MATCHPLAY_API_KEY"` and `"YOUR_MATCHPLAY_USER_ID"` with your actual credentials.

## Usage (Local)

Run the `main.py` script with command-line arguments:

*   **Fetch data from the API and generate the site:**
    ```bash
    python main.py --fetch --generate
    ```
*   **Only fetch data (without generating the site):**
    ```bash
    python main.py --fetch
    ```
*   **Only generate the site (using existing cached data):**
    ```bash
    python main.py --generate
    ```
*   **Generate the site (default behavior if no arguments are provided):**
    ```bash
    python main.py
    ```

After generation, the static HTML files will be located in the `output/` directory. You can open `output/index.html` in your browser to view the site.

## Customization

*   **Excluded Series:** Modify the `EXCLUDED_SERIES_NAMES` list in `config.py` to control which series are included or excluded from the generated statistics.
*   **Templates:** The HTML structure and content can be customized by editing the Jinja2 templates located in the `templates/` directory.
*   **Static Assets:** Update CSS styles or add new static files in the `static/` directory.

## Automated Deployment (GitHub Actions & Pages)

The project is configured for automated deployment to GitHub Pages using GitHub Actions.

1.  **GitHub Actions Workflow:**
    The `.github/workflows/deploy.yml` file defines a workflow that:
    *   Triggers on pushes to the `main` branch.
    *   Runs daily at midnight UTC.
    *   Can be manually triggered from the GitHub Actions tab.
    *   Checks out the code, sets up Python, installs dependencies, fetches data, generates the static site, and pushes the `output/` directory content to the `gh-pages` branch.

2.  **GitHub Secrets:**
    For the automated deployment to work, you **must** add your Matchplay API Key and User ID as repository secrets in your GitHub repository:
    *   Go to your repository on GitHub.
    *   Navigate to `Settings > Secrets and variables > Actions`.
    *   Click "New repository secret" and add:
        *   `MATCHPLAY_API_KEY` (value: your Matchplay API key)
        *   `USER_ID` (value: your Matchplay User ID)

3.  **Enable GitHub Pages:**
    After the first successful workflow run (which creates the `gh-pages` branch):
    *   Go to your repository on GitHub.
    *   Navigate to `Settings > Pages`.
    *   Under "Build and deployment", select "Deploy from a branch".
    *   Choose `gh-pages` as the branch and `/ (root)` as the folder.
    *   Click "Save".

Your static site will then be published at a URL like `https://your-username.github.io/your-repository-name/`.

## Future Enhancements

*   **Player Performance Graphs:** Integrate a JavaScript charting library (e.g., Chart.js) to visualize player performance trends over seasons.
*   **Head-to-Head Statistics:** Develop a feature to compare two players' historical performance against each other.
*   **Advanced Filtering:** Add more sophisticated filtering options for seasons and players.
*   **Improved Mobile Table Display:** Further optimize table presentation for very small screens.
