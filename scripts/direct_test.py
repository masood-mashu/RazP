import os
import sys
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
print(f"Key loaded: {bool(api_key)}")

from google import genai
print("google.genai imported")

client = genai.Client(api_key=api_key)
print("Client created")

# Try generate_content with gemini-2.5-flash and gemini-3.7-flash
model_to_test = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
print(f"Testing model: {model_to_test}")

try:
    response = client.models.generate_content(
        model=model_to_test,
        contents="Say hello in one word",
    )
    print("Response received:", response.text if response else None)
except Exception as e:
    import re
    raw_err = str(e)
    if api_key:
        raw_err = raw_err.replace(api_key, "REDACTED")
    print("Error:", raw_err)
