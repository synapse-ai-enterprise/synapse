"""Helper script to discover Linear team IDs."""

import asyncio
import sys
from pathlib import Path

import aiohttp

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


async def get_linear_teams() -> None:
    """Query Linear API and print team names with their UUIDs."""
    if not settings.linear_api_key:
        print("Error: LINEAR_API_KEY not configured in .env file")
        sys.exit(1)

    query = """
    query {
        teams {
            nodes {
                id
                name
                key
            }
        }
    }
    """

    headers = {
        "Authorization": settings.linear_api_key,
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.linear.app/graphql",
            json={"query": query},
            headers=headers,
        ) as response:
            if response.status != 200:
                print(f"Error: Linear API returned status {response.status}")
                sys.exit(1)

            data = await response.json()
            if "errors" in data:
                print(f"Error: {data['errors']}")
                sys.exit(1)

            teams = data.get("data", {}).get("teams", {}).get("nodes", [])

            if not teams:
                print("No teams found.")
                return

            print("\nLinear Teams:")
            print("=" * 80)
            print(f"{'Team Name':<30} {'Team Key':<15} {'Team ID (UUID)'}")
            print("-" * 80)

            for team in teams:
                name = team.get("name", "Unknown")
                key = team.get("key", "")
                team_id = team.get("id", "")
                print(f"{name:<30} {key:<15} {team_id}")

            print("=" * 80)
            print("\nCopy the Team ID (UUID) and add it to your .env file as LINEAR_TEAM_ID")


if __name__ == "__main__":
    asyncio.run(get_linear_teams())
