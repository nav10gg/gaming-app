import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- SETTINGS ---
# Change this to whatever game mode tournament just ended
TARGET_MODE = "Resurgence" 
POT_TAB_NAME = "Resurgence" # The column name in your Pot tab

def get_winner_data():
    print("Connecting to Google Sheets...")
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open("My Squad Tracker")
    
    # 1. Get the Winning Team
    sheet = spreadsheet.worksheet(TARGET_MODE)
    raw_data = sheet.get_all_values()
    df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
    
    # Clean the data and sort to find 1st Place
    df["Total Score"] = pd.to_numeric(df["Total Score"], errors="coerce")
    df = df.sort_values(by="Total Score", ascending=False)
    
    winning_row = df.iloc[0]
    winning_score = winning_row["Total Score"]
    
    # Stitch the squad names together
    name_cols = [col for col in df.columns if "Name" in col]
    winning_squad = " • ".join([str(val) for val in winning_row[name_cols] if pd.notna(val) and str(val).strip() != ""])
    
    # 2. Get the Final Prize Pool
    pot_sheet = spreadsheet.worksheet("Pot")
    pot_data = pot_sheet.get_all_values()
    headers = pot_data[0]
    total_pot = 0.0
    
    if POT_TAB_NAME in headers:
        col_idx = headers.index(POT_TAB_NAME)
        for row in pot_data[1:]:
            if len(row) > col_idx:
                clean_val = str(row[col_idx]).replace('$', '').replace(',', '').strip()
                if clean_val:
                    total_pot += float(clean_val)
                    
    return winning_squad, winning_score, total_pot

def send_discord_announcement(squad, score, pot):
    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    if not webhook_url:
        print("Error: No Discord Webhook found.")
        return
        
    print(f"Sending announcement for {squad}...")
    
    # Build an epic "Discord Embed"
    embed = {
        "title": "🚨 TOURNAMENT CONCLUDED 🚨",
        "description": f"The **{TARGET_MODE}** season has officially ended. The stats have been locked, the logs have been verified, and the champions have been crowned.",
        "color": 16744448, # This is the decimal code for your Papaya Orange (#FF8000)
        "fields": [
            {
                "name": "🥇 1ST PLACE CHAMPIONS",
                "value": f"**{squad}**",
                "inline": False
            },
            {
                "name": "🔥 Final Score",
                "value": f"{score} pts",
                "inline": True
            },
            {
                "name": "💰 Total Payout",
                "value": f"${pot:,.2f}",
                "inline": True
            }
        ],
        "footer": {
            "text": "Check the League Hub app for the full Hall of Fame breakdown."
        }
    }
    
    payload = {"embeds": [embed]}
    
    response = requests.post(webhook_url, json=payload)
    if response.status_code in [200, 204]:
        print("✅ Announcement successfully sent to Discord!")
    else:
        print(f"❌ Failed to send: {response.status_code} - {response.text}")

if __name__ == "__main__":
    try:
        squad, score, pot = get_winner_data()
        send_discord_announcement(squad, score, pot)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
