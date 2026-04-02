"""
example.py
----------
Three demo profiles for the Kitab Self Map.

Run:
    python example.py
    python example.py --profile 2
    python example.py --all
"""

import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("ASTRO_API_KEY", "")
if not API_KEY:
    sys.exit("Error: ASTRO_API_KEY not found. Add it to your .env file.")

PROFILES = {
    1: {
        "name": "Arjun Sharma", "place": "Mumbai, India",
        "year": 1990, "month": 5, "date": 15,
        "hours": 10, "minutes": 30, "seconds": 0,
        "latitude": 19.076, "longitude": 72.8777, "timezone": 5.5,
    },
    2: {
        "name": "Priya Nair", "place": "Chennai, India",
        "year": 1995, "month": 8, "date": 22,
        "hours": 6, "minutes": 45, "seconds": 0,
        "latitude": 13.0827, "longitude": 80.2707, "timezone": 5.5,
    },
    3: {
        "name": "Rohan Mehta", "place": "Delhi, India",
        "year": 1985, "month": 11, "date": 3,
        "hours": 14, "minutes": 15, "seconds": 0,
        "latitude": 28.6139, "longitude": 77.2090, "timezone": 5.5,
    },
}


def run_profile(profile_id: int) -> None:
    from self_map import generate_self_map, print_summary

    birth = PROFILES[profile_id]
    print(f"\n{'═'*65}")
    print(f"  Generating Self Map for: {birth['name']} (Profile {profile_id})")
    print(f"{'═'*65}")

    result = generate_self_map(birth=birth, api_key=API_KEY, save_chart=True, verbose=True)
    print_summary(result["self_map"])
    print(f"Output: {result['output_dir']}/")


def main():
    parser = argparse.ArgumentParser(description="Kitab Self Map demo")
    parser.add_argument("--profile", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        for pid in [1, 2, 3]:
            run_profile(pid)
    else:
        run_profile(args.profile)


if __name__ == "__main__":
    main()
