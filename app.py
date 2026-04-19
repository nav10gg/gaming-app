import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import os

# 1. Setup for Mobile
st.set_page_config(page_title="League Hub", layout="centered", initial_sidebar_state="collapsed")

# 2. The Sassy Greeting
st.title("🏆 League Hub")
st.info("*Oh, look who decided to check their stats. Still 4th place? Groundbreaking.* — **Unpaid Intern**")
st.divider()

# --- THE GAME MODE DICTIONARY ---
# This links what you see in the app to the exact tabs in your Google Sheet
GAME_MODES = {
    "Ranked Resurgence": {"raw_tab": "Resurgence", "is_quads": True},
    "Ranked WZ Quads": {"raw_tab": "WZ Quads", "is_quads": True},
    "Ranked Avalon Quads": {"raw_tab": "Avalon Quads", "is_quads": True},
    "Ranked Duo Low": {"raw_tab": "Duo Low", "is_quads": False},
    "Ranked Duo High": {"raw_tab": "Duo High", "is_quads": False}
}

# 3. Secure Connection to Google
@st.cache_resource
def init_connection():
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

client = init_connection()
# Make sure this matches your master spreadsheet name perfectly
spreadsheet = client.open("My Squad Tracker") 

# 4. Load the Player Roster (For ID Swapping)
@st.cache_data(ttl=60)
def get_roster():
    try:
        sheet = spreadsheet.worksheet("Draft Room")
        data = sheet.get_all_records()
        # Creates a hidden map: {"Vortex": "<@123456789>", "Shadow": "<@987654321>"}
        return {str(row["Player Name"]): str(row["Discord ID"]) for row in data if row.get("Player Name")}
    except Exception as e:
        st.error(f"Failed to load Draft Room: {e}")
        return {}

# 5. Load the Selected Leaderboard
@st.cache_data(ttl=60)
def get_leaderboard(tab_name):
    try:
        sheet = spreadsheet.worksheet(tab_name)
        raw_data = sheet.get_all_values()
        
        if not raw_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        
        # Base columns every mode uses
        columns_to_keep = ["Total Score", "P1 Name", "P1 Kills", "P2 Name", "P2 Kills"]
        
        # Add P3 and P4 only if it's a Quads mode
        if GAME_MODES[tab_name]["is_quads"]:
            columns_to_keep.extend(["P3 Name", "P3 Kills", "P4 Name", "P4 Kills"]) 
            
        safe_columns = [col for col in columns_to_keep if col in df.columns]
        df = df[safe_columns]
        
        if "Total Score" in df.columns:
            df["Total Score"] = pd.to_numeric(df["Total Score"], errors="coerce")
            df = df.sort_values(by="Total Score", ascending=False)
            
        return df
    except Exception as e:
        st.error(f"Failed to load {tab_name}: {e}")
        return pd.DataFrame()

# --- APP INTERFACE ---

# The Game Mode Dropdown
selected_mode = st.selectbox("🎮 Select Game Mode", list(GAME_MODES.keys()))
is_quads = GAME_MODES[selected_mode]["is_quads"]
raw_target_tab = GAME_MODES[selected_mode]["raw_tab"]

roster_dict = get_roster()
# Create a list of names for the dropdown, starting with a blank option
player_names = [""] + list(roster_dict.keys()) 

# Display the Leaderboard
df = get_leaderboard(selected_mode)
if not df.empty:
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("No data found for this mode.")

st.divider()

# --- THE ACTION PORTAL (MATCH SUBMISSION) ---
st.subheader(f"📝 Submit Match: {selected_mode}")

with st.form("match_submission_form", clear_on_submit=True):
    total_score = st.number_input("Total Score", min_value=0, step=1)
    
    col1, col2 = st.columns(2)
    with col1:
        p1_name = st.selectbox("Player 1", player_names)
        p1_kills = st.number_input("P1 Kills", min_value=0, step=1)
    with col2:
        p2_name = st.selectbox("Player 2", player_names)
        p2_kills = st.number_input("P2 Kills", min_value=0, step=1)
        
    if is_quads:
        col3, col4 = st.columns(2)
        with col3:
            p3_name = st.selectbox("Player 3", player_names)
            p3_kills = st.number_input("P3 Kills", min_value=0, step=1)
        with col4:
            p4_name = st.selectbox("Player 4", player_names)
            p4_kills = st.number_input("P4 Kills", min_value=0, step=1)
            
    submit_button = st.form_submit_button("Log Match")
    
    if submit_button:
        # Require at least P1 to be filled out
        if not p1_name:
            st.error("You must select at least Player 1.")
        else:
            # Secretly swap the names for Discord IDs
            p1_id = roster_dict.get(p1_name, p1_name)
            p2_id = roster_dict.get(p2_name, p2_name) if p2_name else ""
            
            # Build the array of data to send to Google Sheets
            # **IMPORTANT**: This assumes your raw drop zone tabs have Total Score in Column A, P1 in Column B, etc.
            if is_quads:
                p3_id = roster_dict.get(p3_name, p3_name) if p3_name else ""
                p4_id = roster_dict.get(p4_name, p4_name) if 'p4_name' in locals() and p4_name else ""
                new_row = [total_score, p1_id, p1_kills, p2_id, p2_kills, p3_id, p3_kills, p4_id, p4_kills]
            else:
                new_row = [total_score, p1_id, p1_kills, p2_id, p2_kills]
                
            try:
                # Push the new row to the bottom of the raw data tab
                target_sheet = spreadsheet.worksheet(raw_target_tab)
                target_sheet.append_row(new_row)
                
                # Clear the cache so the leaderboard instantly refreshes with the new score
                st.cache_data.clear()
                st.success(f"✅ Match logged successfully to {raw_target_tab}! Score Bot has been notified.")
                
            except Exception as e:
                st.error(f"Failed to submit match to sheet: {e}")
