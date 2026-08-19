"""Standalone, no-Django script: list every model the API key can call.
Usage: python scripts/list_gemini_models.py
"""
import os

from dotenv import load_dotenv
from google import genai

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_DEV_KEY")
if not api_key:
    raise SystemExit("No GEMINI_API_KEY or GEMINI_DEV_KEY found in backend/.env")

client = genai.Client(api_key=api_key)

for model in client.models.list():
    print(model.name)
