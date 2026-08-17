#!/usr/bin/env python3
from pathlib import Path
import os
from dotenv import load_dotenv

# Check .env loading
PROJECT_ROOT = Path(__file__).resolve().parent
env_path = PROJECT_ROOT / ".env"

print(f"Root: {PROJECT_ROOT}")
print(f"Env path: {env_path}")
print(f"Exists: {env_path.exists()}")

if env_path.exists():
    print("\nFile contents:")
    with open(env_path) as f:
        lines = f.readlines()
        for line in lines:
            if line.strip():
                key = line.split('=')[0]
                print(f"  {key}=...")

load_dotenv(env_path)

print("\nLoaded variables:")
print(f"  DISCORD_BOT_TOKEN={os.getenv('DISCORD_BOT_TOKEN', 'MISSING')[:20]}...")
print(f"  TELEGRAM_BOT_TOKEN={os.getenv('TELEGRAM_BOT_TOKEN', 'MISSING')[:20]}...")
print(f"  WIKI_BASE_URL={os.getenv('WIKI_BASE_URL', 'MISSING')}")
print(f"  LOG_LEVEL={os.getenv('LOG_LEVEL', 'MISSING')}")
