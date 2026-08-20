import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

try:
    response = model.generate_content("Responda apenas 'OK'", generation_config={"response_mime_type": "text/plain"})
    print(f"Status Gemini: {response.text.strip()}")
except Exception as e:
    print(f"Erro Gemini: {e}")
