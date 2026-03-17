import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
print(f"Using API Key: {api_key[:5]}...{api_key[-5:] if api_key else ''}")

try:
    genai.configure(api_key=api_key)
    print("Listing models...")
    for m in genai.list_models():
        print(f"Name: {m.name}, Display: {m.display_name}, Supported: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error listing models: {e}")
