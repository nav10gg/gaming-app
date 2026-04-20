import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import os
import requests

# 1. Setup for Mobile
st.set_page_config(page_title="League Hub", layout="centered", initial_sidebar_state="collapsed")

# 2. The Sassy Greeting
st.title("🏆 League Hub")
st.info("*Oh, look who decided to check their stats. Still 4th place? Groundbreaking.* — **Unpaid Intern**")
st.divider()

# --- THE GAME MODE DICTIONARY ---
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
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

client = init_connection()
spreadsheet = client.open("My Squad Tracker") 

# 4. Load the Player Roster 
@st.cache_data(ttl=60)
def get_roster():
    try:
        sheet = spreadsheet.worksheet("Draft Room")
        data = sheet.get_all_records()
        return {str(row["Player Name"]): str(row["Discord ID"]) for row in data if row.get("Player Name")}
    except:
        return {}

# 5. Load the Selected Leaderboard
@st.cache_data(ttl=60)
def get_leaderboard(tab_name):
    try:
        sheet = spreadsheet.worksheet(tab_name)
        raw_data = sheet.get_all_values()
        if not raw_data: return pd.DataFrame()
        
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        columns_to_keep = ["Total Score", "P1 Name", "P1 Kills", "P2 Name", "P2 Kills"]
        
        if GAME_MODES[tab_name]["is_quads"]:
            columns_to_keep.extend(["P3 Name", "P3 Kills", "P4 Name", "P4 Kills"]) 
            
        safe_columns = [col for col in columns_to_keep if col in df.columns]
        df = df[safe_columns]
        
        if "Total Score" in df.columns:
            df["Total Score"] = pd.to_numeric(df["Total Score"], errors="coerce")
            df = df.sort_values(by="Total Score", ascending=False)
            
        return df
    except:
        return pd.DataFrame()

# 6. Discord Webhook Logic
def upload_to_discord(file_bytes, filename, message):
    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    if not webhook_url: return None
    
    url = f"{webhook_url}?wait=true"
    payload = {"content": message}
    files = {"file": (filename, file_bytes)}
    
    try:
        response = requests.post(url, data=payload, files=files)
        if response.status_code in [200, 201]:
            data = response.json()
            return data["attachments"][0]["url"]
    except Exception as e:
        print(f"Webhook failed: {e}")
    return None

# --- APP INTERFACE ---

selected_mode = st.selectbox("🎮 Select Game Mode", list(GAME_MODES.keys()))
is_quads = GAME_MODES[selected_mode]["is_quads"]
raw_target_tab = GAME_MODES[selected_mode]["raw_tab"]

roster_dict = get_roster()
player_names = [""] + list(roster_dict.keys()) 

df = get_leaderboard(selected_mode)
if not df.empty:
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- CONSECUTIVE TICKET GENERATOR ---
st.subheader(f"📝 Submit Match: {selected_mode}")

# 1. If there isn't an active ticket, find the highest existing one in the sheet and add 1
if 'ticket_number' not in st.session_state:
    try:
        target_sheet = spreadsheet.worksheet(raw_target_tab)
        headers = target_sheet.row_values(1)
        
        if "Ticket Number" in headers:
            # Find which column holds the Ticket Numbers
            col_index = headers.index("Ticket Number") + 1
            existing_tickets = target_sheet.col_values(col_index)[1:] # Skip the header
            
            ticket_nums = []
            for t in existing_tickets:
                try:
                    ticket_nums.append(int(t))
                except ValueError:
                    pass # Ignore blanks or text
                    
            # Set the ticket to the highest number + 1 (Start at 100 if completely empty)
            st.session_state.ticket_number = max(ticket_nums) + 1 if ticket_nums else 100
        else:
            st.session_state.ticket_number = 100
            
    except Exception as e:
        st.session_state.ticket_number = 999 # Fallback if something goes wrong

# 2. Display the Active Ticket
st.info(f"🎫 **Active Ticket Number:** {st.session_state.ticket_number}")

# 3. The reset button for when they finish a run
if st.button("🔄 End Run & Start New Ticket"):
    del st.session_state.ticket_number
    st.rerun()

# --- THE ACTION PORTAL ---
with st.form("match_submission_form", clear_on_submit=True):
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        game_num = st.selectbox("Game Number", [1, 2, 3, 4, 5, 6])
    with col_g2:
        placement = st.number_input("Placement (e.g., 1 for 1st)", min_value=1, step=1)
    
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
            
    uploaded_file = st.file_uploader("📸 Upload Screenshot (Optional)", type=["png", "jpg", "jpeg"])
            
    submit_button = st.form_submit_button("Log Match")
    
    if submit_button:
        if not p1_name:
            st.error("You must select at least Player 1.")
        else:
            p1_id = roster_dict.get(p1_name, p1_name)
            p2_id = roster_dict.get(p2_name, p2_name) if p2_name else ""
            p3_id = roster_dict.get(p3_name, p3_name) if 'p3_name' in locals() and p3_name else ""
            p4_id = roster_dict.get(p4_name, p4_name) if 'p4_name' in locals() and p4_name else ""

            image_url = ""
            if uploaded_file:
                discord_msg = f"**📝 NEW MATCH LOGGED**\n**Mode:** {selected_mode}\n**Ticket:** {st.session_state.ticket_number}\n**Game:** {game_num}\n**Placement:** {placement}\n**Submitted By:** {p1_name}"
                image_url = upload_to_discord(uploaded_file.getvalue(), uploaded_file.name, discord_msg)
                
            target_sheet = spreadsheet.worksheet(raw_target_tab)
            headers = target_sheet.row_values(1)
            new_row = [""] * len(headers) 
            
            def safe_insert(col_name, value):
                if col_name in headers:
                    new_row[headers.index(col_name)] = value
                    
            # Inject the current consecutive ticket number
            safe_insert("Ticket Number", st.session_state.ticket_number)
            
            safe_insert(f"G{game_num} Placement", placement)
            safe_insert(f"G{game_num} P1 Name", p1_id)
            safe_insert(f"G{game_num} P1 Kills", p1_kills)
            safe_insert(f"G{game_num} P2 Name", p2_id)
            safe_insert(f"G{game_num} P2 Kills", p2_kills)
            if is_quads:
                safe_insert(f"G{game_num} P3 Name", p3_id)
                safe_insert(f"G{game_num} P3 Kills", p3_kills)
                safe_insert(f"G{game_num} P4 Name", p4_id)
                safe_insert(f"G{game_num} P4 Kills", p4_kills)
            
            safe_insert("Screenshot Link", image_url if image_url else "No Image")

            try:
                target_sheet.append_row(new_row)
                st.cache_data.clear()
                st.success(f"✅ Game {game_num} (Ticket {st.session_state.ticket_number}) logged successfully! Image sent to Discord: {'Yes' if image_url else 'No'}")
            except Exception as e:
                st.error(f"Failed to submit match to sheet: {e}")
