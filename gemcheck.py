from google import genai
import os
from dotenv import load_dotenv
load_dotenv()  # this slurps up .env into os.environ

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Pass it into the client
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Say hi in one short sentence."
)

print(response.text)
