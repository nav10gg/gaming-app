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

# 3. Connect to Google Sheets Securely
@st.cache_data(ttl=60) # This tells Streamlit to only ping Google once a minute so we don't hit API limits
def load_data():
    try:
        # Load the credentials from Railway's environment variables
        creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open the specific sheet (Swap this name if needed!)
        sheet = client.open("My Squad Tracker").Ranked Resurgence 
        
        # Pull all the data into a Pandas DataFrame
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return pd.DataFrame() # Return empty table if it fails

# Load the real data
df = load_data()

# 4. Display the Data (Only if we successfully loaded it)
if not df.empty:
    st.subheader("📊 Live Leaderboard")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("No data found or connection failed.")

st.divider()

# 5. Action Portal (To trigger Score Bot later)
st.subheader("📝 Submit Match Result")
# We will build the submission form logic next!
