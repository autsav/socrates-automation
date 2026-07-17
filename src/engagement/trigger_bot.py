"""Trigger the engagement bot for a manually-posted Reel.

Usage after you manually post to Instagram:
    python -m src.engagement.trigger_bot <post_id> [--quote "the quote text"]

The pipeline sends you the Reel via Telegram. You post it manually with
trending audio. Instagram gives you the post_id. You run this script
with that post_id, and the bot takes over: fetching comments and replying
for 30 minutes.
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Run the engagement bot for a manually-posted Instagram Reel."
    )
    parser.add_argument("post_id", help="The Instagram media_id of your posted Reel")
    parser.add_argument("--quote", default="", help="The quote text (for context-aware replies)")
    parser.add_argument("--rounds", type=int, default=6, help="Number of reply rounds (6 = 30 min)")
    parser.add_argument("--delay", type=int, default=0, help="Initial delay in seconds (0 = start now)")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    token = os.getenv("META_ACCESS_TOKEN", "")

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Needed for AI replies.")
        sys.exit(1)
    if not token:
        print("ERROR: META_ACCESS_TOKEN not set. Needed to fetch comments.")
        sys.exit(1)

    from src.engagement.engagement_bot import run_engagement_bot

    print(f"Starting engagement bot for post {args.post_id}")
    print(f"  Rounds: {args.rounds}")
    print(f"  Delay: {args.delay}s")
    print(f"  Quote context: {args.quote[:50]}..." if args.quote else "  No quote context")

    stats = run_engagement_bot(
        media_id=args.post_id,
        access_token=token,
        anthropic_api_key=api_key,
        post_quote=args.quote,
        max_rounds=args.rounds,
        delay_sec=args.delay,
    )

    print(f"\nDone: {stats['replied']} replied, {stats['skipped']} skipped, {stats['errors']} errors")


if __name__ == "__main__":
    main()