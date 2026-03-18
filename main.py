import argparse
import os
import sys
from dotenv import load_dotenv

import api_client
from api_client import fetch_data, API_KEY, USER_ID
from data_processor import load_finals_mapping, parse_series_name
from site_generator import generate_site
from config import EXCLUDED_SERIES_NAMES, TEMPLATES_DIR

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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass cache staleness check and re-fetch all data."
    )
    args = parser.parse_args()

    # Default to generating the site if no arguments are provided
    should_generate = args.generate or not (args.fetch)

    if args.fetch:
        if not API_KEY or not USER_ID or "YOUR_" in API_KEY:
            print("ERROR: MATCHPLAY_API_KEY and USER_ID must be set to fetch data.")
            sys.exit(1)
        if args.force:
            api_client.FORCE_REFRESH = True
            print("--- Force refresh enabled: ignoring cache ---")
        print("--- Starting Data Fetch ---")
        fetch_data(EXCLUDED_SERIES_NAMES, load_finals_mapping(), parse_series_name)
        print("--- Data Fetch Complete ---")

    if should_generate:
        print("--- Starting Site Generation ---")
        generate_site(EXCLUDED_SERIES_NAMES)
        print("--- Site Generation Complete ---")

if __name__ == "__main__":
    main()
