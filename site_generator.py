import os
import shutil
from jinja2 import Environment, FileSystemLoader

from data_processor import load_all_series_data
from config import OUTPUT_DIR, TEMPLATES_DIR, STATIC_DIR
from page_generators.helpers import score_color_filter, format_number_filter, json_attribute_filter
from page_generators.seasons import generate_seasons_page, generate_season_pages
from page_generators.players import generate_player_pages
from page_generators.charts import generate_charts_page
from page_generators.leaderboards import generate_leaderboards_page

def generate_site(excluded_series_names):
    """Generates the static HTML site."""
    print("Generating static site...")
    
    # Clean and recreate OUTPUT_DIR to ensure fresh generation
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True) # Recreate after deletion
    
    # Copy static files to output directory
    static_output_dir = os.path.join(OUTPUT_DIR, 'static')
    if os.path.exists(static_output_dir):
        shutil.rmtree(static_output_dir)
    shutil.copytree(STATIC_DIR, static_output_dir)
    print(f"Copied static files from '{STATIC_DIR}' to '{static_output_dir}'")

    all_series_data = load_all_series_data(excluded_series_names)

    if not all_series_data:
        print("\nNo data found in the 'data' directory.")
        print("Please run the script with fetch_data() enabled to download the data first.")
        return
    
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters['score_color_code'] = score_color_filter # Register the custom filter
    env.filters['format_number'] = format_number_filter # Register the new filter
    env.filters['tojson'] = json_attribute_filter # Register our custom safe JSON filter

    template = env.get_template('index.html')
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w') as f:
        f.write(template.render())
    print("Generated index.html")

    generate_seasons_page(env, all_series_data)
    generate_season_pages(env, all_series_data)
    player_categorized_seasons, all_players_chart_data = generate_player_pages(env, all_series_data)
    generate_charts_page(env, all_players_chart_data) # New call to generate charts page
    generate_leaderboards_page(env, all_series_data, player_categorized_seasons)
