import argparse
from dotenv import load_dotenv

from api_client import fetch_data, API_KEY, USER_ID
from data_processor import load_finals_mapping, parse_series_name
from site_generator import generate_site
from config import EXCLUDED_SERIES_NAMES

load_dotenv()

def main():
    """
    Main function to fetch data and/or generate the static site.
    """
    parser = argparse.ArgumentParser(description="MFP Stats Site Generator")
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch the latest data from the Matchplay API."
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate the static HTML site."
    )
    args = parser.parse_args()

    # Default to generating the site if no arguments are provided
    should_generate = args.generate or not (args.fetch)

    if not API_KEY or not USER_ID or "YOUR_" in API_KEY:
        print("Please create a .env file and add your MATCHPLAY_API_KEY and USER_ID.")
        return

    if args.fetch:
        print("--- Starting Data Fetch ---")
        fetch_data(EXCLUDED_SERIES_NAMES, load_finals_mapping(), parse_series_name)
        print("--- Data Fetch Complete ---")

    if should_generate:
        print("--- Starting Site Generation ---")
        generate_site(EXCLUDED_SERIES_NAMES)
        print("--- Site Generation Complete ---")

if __name__ == "__main__":
    main()
