import os
from config import OUTPUT_DIR

def generate_charts_page(env, all_players_chart_data):
    """Generates the charts.html page."""
    print("Generating charts.html...")
    template = env.get_template('charts.html')
    with open(os.path.join(OUTPUT_DIR, 'charts.html'), 'w') as f:
        # Pass the Python dictionary directly; the 'tojson' filter in the template will handle serialization and escaping
        f.write(template.render(all_players_chart_data=all_players_chart_data))
    print("Generated charts.html")
