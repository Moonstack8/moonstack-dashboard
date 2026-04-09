import requests
from dotenv import load_dotenv
import os

load_dotenv()

AD_ACCOUNT_ID = os.getenv("AD_ACCOUNT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

res = requests.post(
    f"https://graph.facebook.com/v21.0/{AD_ACCOUNT_ID}/campaigns",
    params={
        "name": "My First Campaign",
        "objective": "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "special_ad_categories": "[]",
        "is_adset_budget_sharing_enabled": "false",
        "access_token": ACCESS_TOKEN
    }
)

data = res.json()
print(data)

if "id" in data:
    print(f"Campaign created! ID: {data['id']}")