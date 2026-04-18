import streamlit as st
import pandas as pd

# 1. Setup for Mobile
st.set_page_config(page_title="League Hub", layout="centered", initial_sidebar_state="collapsed")

# 2. The Sassy Greeting
st.title("🏆 League Hub")
st.info("*Oh, look who decided to check their stats. Still 4th place? Groundbreaking.* — **Unpaid Intern**")
st.divider()

# 3. Mock Data (We will swap this for your Google Sheet later)
data = {
    "Player": ["Vortex", "Shadow", "Rogue", "Ghost"],
    "Wins": [15, 12, 10, 4],
    "Losses": [2, 5, 6, 15],
    "Win Rate": ["88%", "70%", "62%", "21%"],
    "Affinity": ["Favored", "Neutral", "Target", "Burn Book"]
}
df = pd.DataFrame(data)

# 4. Mobile-Friendly Top Stats
st.subheader("📊 Live Leaderboard")
col1, col2 = st.columns(2)
col1.metric(label="Current Leader", value=df["Player"].iloc[0], delta="+3 Wins")
col2.metric(label="Biggest Drop", value=df["Player"].iloc[-1], delta="-5 Wins", delta_color="inverse")

# 5. The Data Table
# use_container_width ensures it snaps perfectly to a phone screen
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# 6. Action Portal (To trigger TrashBot later)
st.subheader("📝 Submit Match Result")
with st.form("match_form"):
    player_name = st.selectbox("Select Player", df["Player"])
    result = st.radio("Result", ["Win", "Loss"], horizontal=True)
    submitted = st.form_submit_button("Log Match")
    
    if submitted:
        st.success(f"Score logged for {player_name}. TrashBot has been notified.")
