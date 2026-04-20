import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import os
import requests
import uuid

# 1. Setup for Mobile
st.set_page_config(page_title="League Hub", layout="centered", initial_sidebar_state="collapsed")

# 2. The Sassy Greeting (Now Bulletproof)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if os.path.exists("main_logo.png"):
        st.image("main_logo.png", width="stretch")
    else:
        st.markdown("<h1 style='text-align: center;'>🏆 League Hub</h1>", unsafe_allow_html=True)

st.info("*Oh, look who decided to check their stats. Still 4th place? Groundbreaking.* — **Unpaid Intern**")

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

# 5.5 Load Lifetime Stats
@st.cache_data(ttl=60)
def get_lifetime_stats():
    try:
        sheet = spreadsheet.worksheet("Lifetime Stats")
        raw_data = sheet.get_all_values()
        if not raw_data: return pd.DataFrame()
        
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        return df
    except:
        return pd.DataFrame()

# 5.6 Load The Prize Pool
@st.cache_data(ttl=60)
def get_prize_pool(target_column):
    try:
        sheet = spreadsheet.worksheet("Pot")
        raw_data = sheet.get_all_values()
        if not raw_data: return 0.0
        
        headers = raw_data[0]
        if target_column in headers:
            col_idx = headers.index(target_column)
            col_vals = [row[col_idx] for row in raw_data[1:] if len(row) > col_idx]
            
            total_pot = 0.0
            for val in col_vals:
                try:
                    clean_val = str(val).replace('$', '').replace(',', '').strip()
                    if clean_val:
                        total_pot += float(clean_val)
                except:
                    pass
            return total_pot
    except:
        return 0.0
    return 0.0

# 6. Discord Webhook Logic 
def upload_to_discord(file_bytes, filename, message):
    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    if not webhook_url: return None
    
    url = f"{webhook_url}?wait=true"
    payload = {"content": message}
    files = {"file": (filename, file_bytes)}
    
    try:
        response = requests.post(url, data=payload, files=files, timeout=10)
        if response.status_code in [200, 201]:
            data = response.json()
            return data["attachments"][0]["url"]
    except requests.exceptions.Timeout:
        print("Webhook timeout: Discord took too long to respond.")
    except Exception as e:
        print(f"Webhook failed: {e}")
    return None

# ==========================================
# --- APP INTERFACE & NAVIGATION ROUTING ---
# ==========================================

page = st.radio("Navigation", ["🏆 Leaderboard", "👑 Hall of Fame", "📝 Submit Match"], horizontal=True, label_visibility="collapsed")
st.divider()

selected_mode = st.selectbox("🎮 Select Game Mode", list(GAME_MODES.keys()))
is_quads = GAME_MODES[selected_mode]["is_quads"]
raw_target_tab = GAME_MODES[selected_mode]["raw_tab"]

roster_dict = get_roster()
player_names = [""] + list(roster_dict.keys()) 

st.divider()

# ==========================================
# PAGE 1: THE LEADERBOARD
# ==========================================
if page == "🏆 Leaderboard":
    df = get_leaderboard(selected_mode)
    pot_total = get_prize_pool(raw_target_tab)

    if not df.empty:
        name_cols = [col for col in df.columns if "Name" in col]
        df["Squad"] = df[name_cols].apply(lambda row: " • ".join([str(val) for val in row if pd.notna(val) and str(val).strip() != ""]), axis=1)
        
        top_squads = df["Squad"].tolist()
        top_scores = df["Total Score"].tolist()
        
        while len(top_squads) < 3:
            top_squads.append("TBD")
            top_scores.append(0)

        # Show the massive Prize Pool Banner
        st.markdown(f"<h2 style='text-align: center; color: #FF8000;'>💰 Live Prize Pool: ${pot_total:,.2f}</h2>", unsafe_allow_html=True)
        st.write("")

        st.subheader("🏁 Top 3 Podium")
        
        with st.container(border=True):
            logo_col, text_col = st.columns([1, 3], vertical_alignment="center")
            with logo_col:
                if os.path.exists("first_place.png"):
                    st.image("first_place.png", width=60)
                else:
                    st.markdown("## 🥇")
            with text_col:
                st.markdown("### 1st Place")
                st.markdown(f"**{top_squads[0]}**")
            st.success(f"🏆 {top_scores[0]} pts  |  💰 Takes ${pot_total:,.2f}") 

        with st.container(border=True):
            logo_col, text_col = st.columns([1, 3], vertical_alignment="center")
            with logo_col:
                if os.path.exists("second_place.png"):
                    st.image("second_place.png", width=50)
                else:
                    st.markdown("## 🥈")
            with text_col:
                st.markdown("#### 2nd Place")
                st.markdown(f"**{top_squads[1]}**")
            st.info(f"⚡ {top_scores[1]} pts") 

        with st.container(border=True):
            logo_col, text_col = st.columns([1, 3], vertical_alignment="center")
            with logo_col:
                if os.path.exists("third_place.png"):
                    st.image("third_place.png", width=50)
                else:
                    st.markdown("## 🥉")
            with text_col:
                st.markdown("#### 3rd Place")
                st.markdown(f"**{top_squads[2]}**")
            st.warning(f"🔥 {top_scores[2]} pts") 
            
        st.divider()

        st.subheader("📊 The Contenders")
        if len(df) > 3:
            contenders_df = df.iloc[3:].copy()
            max_score = float(df["Total Score"].max())
            if pd.isna(max_score) or max_score <= 0: max_score = 1.0 
                
            with st.container(height=500, border=True):
                for index, row in contenders_df.iterrows():
                    squad = row['Squad']
                    score = float(row['Total Score']) if pd.notna(row['Total Score']) else 0.0
                    progress_pct = min(score / max_score, 1.0) if score > 0 else 0.0
                    
                    st.markdown(f"**{squad}**")
                    st.progress(progress_pct, text=f"{score} pts")
                    st.write("") 
        else:
            st.info("Not enough teams to fill the Contenders bracket yet. Log some matches!")

# ==========================================
# PAGE 2: HALL OF FAME 
# ==========================================
elif page == "👑 Hall of Fame":
    lifetime_df = get_lifetime_stats()

    if not lifetime_df.empty and "Player Name" in lifetime_df.columns:
        lifetime_df = lifetime_df[lifetime_df["Player Name"].str.strip() != ""]

        # --- 1. MODE-SPECIFIC LEADERBOARD ---
        st.subheader(f"👑 {selected_mode} Legends")
        
        prefix = GAME_MODES[selected_mode]["raw_tab"]
        mode_kill_col = f"{prefix} Kills"
        mode_game_col = f"{prefix} Games"

        if mode_kill_col in lifetime_df.columns and mode_game_col in lifetime_df.columns:
            mode_df = lifetime_df[["Player Name", mode_game_col, mode_kill_col]].copy()
            mode_df[mode_game_col] = pd.to_numeric(mode_df[mode_game_col], errors="coerce").fillna(0)
            mode_df[mode_kill_col] = pd.to_numeric(mode_df[mode_kill_col], errors="coerce").fillna(0)
            
            mode_df = mode_df[mode_df[mode_game_col] > 0].copy()
            
            if not mode_df.empty:
                mode_df["Avg Kills/Game"] = mode_df[mode_kill_col] / mode_df[mode_game_col]
                mode_df = mode_df.sort_values(by="Avg Kills/Game", ascending=False)
                
                mvp_name = mode_df.iloc[0]["Player Name"]
                mvp_avg = mode_df.iloc[0]["Avg Kills/Game"]
                
                st.metric(label=f"🌟 {selected_mode} MVP", value=mvp_name, delta=f"{mvp_avg:.2f} Avg Kills / Match")
                
                max_mode_avg = float(mode_df["Avg Kills/Game"].max())
                st.dataframe(
                    mode_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Player Name": st.column_config.TextColumn("Legend"),
                        mode_game_col: st.column_config.NumberColumn("Matches", format="%d"),
                        mode_kill_col: st.column_config.NumberColumn("Kills", format="%d"),
                        "Avg Kills/Game": st.column_config.ProgressColumn(
                            "Avg Kills / Match",
                            format="%.2f",
                            min_value=0,
                            max_value=max_mode_avg,
                        )
                    }
                )
            else:
                st.info(f"No matches recorded for {selected_mode} yet.")
        else:
            st.warning(f"Could not find columns for {selected_mode} in Lifetime Stats tab.")

        st.divider()

        # --- 2. ALL-TIME OVERALL STATS ---
        st.subheader("♾️ All-Time Lifetime Legends")
        
        kill_cols = [col for col in lifetime_df.columns if "Kills" in col]
        game_cols = [col for col in lifetime_df.columns if "Games" in col]

        all_time_df = lifetime_df[["Player Name"] + kill_cols + game_cols].copy()
        for col in kill_cols + game_cols:
            all_time_df[col] = pd.to_numeric(all_time_df[col], errors="coerce").fillna(0)

        all_time_df["Total Games"] = all_time_df[game_cols].sum(axis=1)
        all_time_df["Total Kills"] = all_time_df[kill_cols].sum(axis=1)
        
        all_time_df = all_time_df[all_time_df["Total Games"] > 0].copy()
        
        if not all_time_df.empty:
            all_time_df["Avg Kills/Game"] = all_time_df["Total Kills"] / all_time_df["Total Games"]
            all_time_df = all_time_df.sort_values(by="Avg Kills/Game", ascending=False)
            
            final_board = all_time_df[["Player Name", "Total Games", "Total Kills", "Avg Kills/Game"]]
            max_avg = float(final_board["Avg Kills/Game"].max())
            
            st.dataframe(
                final_board,
                width="stretch",
                hide_index=True,
                column_config={
                    "Player Name": st.column_config.TextColumn("Legend", width="medium"),
                    "Total Games": st.column_config.NumberColumn("Total Matches", format="%d"),
                    "Total Kills": st.column_config.NumberColumn("Total Kills", format="%d"),
                    "Avg Kills/Game": st.column_config.ProgressColumn(
                        "Overall Avg / Match",
                        format="%.2f",
                        min_value=0,
                        max_value=max_avg,
                    )
                }
            )
        else:
            st.info("No lifetime data available yet.")
    else:
        st.warning("Could not load the 'Lifetime Stats' tab or find the 'Player Name' column.")

# ==========================================
# PAGE 3: SUBMIT MATCH 
# ==========================================
elif page == "📝 Submit Match":
    st.subheader(f"📝 Submit Match: {selected_mode}")

    if 'ticket_number' not in st.session_state:
        try:
            target_sheet = spreadsheet.worksheet(raw_target_tab)
            headers = target_sheet.row_values(1)
            
            if "Ticket Number" in headers:
                col_index = headers.index("Ticket Number") + 1
                existing_tickets = target_sheet.col_values(col_index)[1:] 
                
                ticket_nums = []
                for t in existing_tickets:
                    try:
                        ticket_nums.append(int(str(t).split('-')[0])) 
                    except ValueError:
                        pass 
                        
                next_num = max(ticket_nums) + 1 if ticket_nums else 100
                random_suffix = str(uuid.uuid4())[:3].upper()
                st.session_state.ticket_number = f"{next_num}-{random_suffix}"
                
        except Exception as e:
            st.session_state.ticket_number = 999 

    st.info(f"🎫 **Active Ticket Number:** {st.session_state.ticket_number}")

    if st.button("🔄 End Run & Start New Ticket"):
        del st.session_state.ticket_number
        st.rerun()

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
            selected_players = [p1_name, p2_name]
            if is_quads:
                selected_players.extend([p3_name, p4_name])
            
            active_players = [p for p in selected_players if p != ""]
            
            if not p1_name:
                st.error("You must select at least Player 1.")
            elif len(active_players) != len(set(active_players)):
                st.error("Duplicate players detected! You can't put the same person in two slots.")
            else:
                p1_id = roster_dict.get(p1_name, p1_name)
                p2_id = roster_dict.get(p2_name, p2_name) if p2_name else ""
                p3_id = roster_dict.get(p3_name, p3_name) if 'p3_name' in locals() and p3_name else ""
                p4_id = roster_dict.get(p4_name, p4_name) if 'p4_name' in locals() and p4_name else ""

                image_url = ""
                if uploaded_file:
                    discord_msg = f"**📝 NEW MATCH LOGGED**\n**Mode:** {selected_mode}\n**Ticket:** {st.session_state.ticket_number}\n**Game:** {game_num}\n**Placement:** {placement}\n**Submitted By:** {p1_name}"
                    with st.spinner("Uploading screenshot to Discord..."):
                        image_url = upload_to_discord(uploaded_file.getvalue(), uploaded_file.name, discord_msg)
                        if not image_url:
                            st.toast("⚠️ Discord upload failed, but logging match anyway!", icon="⚠️")
                    
                target_sheet = spreadsheet.worksheet(raw_target_tab)
                headers = target_sheet.row_values(1)
                
                new_game_data = {
                    "Ticket Number": st.session_state.ticket_number,
                    f"G{game_num} Placement": placement,
                    f"G{game_num} P1 Name": p1_id,
                    f"G{game_num} P1 Kills": p1_kills,
                    f"G{game_num} P2 Name": p2_id,
                    f"G{game_num} P2 Kills": p2_kills,
                    "Screenshot Link": image_url if image_url else ""
                }
                
                if is_quads:
                    new_game_data.update({
                        f"G{game_num} P3 Name": p3_id,
                        f"G{game_num} P3 Kills": p3_kills,
                        f"G{game_num} P4 Name": p4_id,
                        f"G{game_num} P4 Kills": p4_kills
                    })

                try:
                    ticket_col_index = headers.index("Ticket Number") + 1
                    
                    try:
                        cell = target_sheet.find(st.session_state.ticket_number, in_column=ticket_col_index)
                        row_num = cell.row
                        current_row = target_sheet.row_values(row_num)
                        current_row += [""] * (len(headers) - len(current_row))
                        
                        for col_name, val in new_game_data.items():
                            if col_name in headers and val != "":
                                idx = headers.index(col_name)
                                current_row[idx] = val
                                
                        target_sheet.update(values=[current_row], range_name=f"A{row_num}")
                        action_taken = "Updated"

                    except Exception: 
                        new_row = [""] * len(headers)
                        for col_name, val in new_game_data.items():
                            if col_name in headers:
                                new_row[headers.index(col_name)] = val
                        
                        target_sheet.append_row(new_row)
                        action_taken = "Logged"

                    st.cache_data.clear()
                    st.success(f"✅ Game {game_num} (Ticket {st.session_state.ticket_number}) {action_taken} successfully!")
                    
                except Exception as e:
                    st.error(f"Failed to submit match to sheet: {e}")
