import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_client = genai.Client(api_key=GEMINI_API_KEY)


def generate_content(prompt: str, model_name: str = "gemini-2.5-flash-lite", json_mode: bool = False) -> str:
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if json_mode else "text/plain"
    )
    response = _client.models.generate_content(model=model_name, contents=prompt, config=config)
    return response.text
