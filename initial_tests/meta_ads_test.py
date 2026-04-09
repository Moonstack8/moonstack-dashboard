import requests

from dotenv import load_dotenv
import os

load_dotenv()

AD_ACCOUNT_ID = os.getenv("AD_ACCOUNT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

res = requests.get(
    f"https://graph.facebook.com/v21.0/{AD_ACCOUNT_ID}/campaigns",
    params={
        "fields": "id,name,status,objective",
        "access_token": ACCESS_TOKEN
    }
)

data = res.json()
print(data)

if "error" in data:
    print("Error:", data["error"]["message"])
else:
    for campaign in data["data"]:
        print(f"Campaign: {campaign['name']} | Status: {campaign['status']} | Objective: {campaign['objective']}")