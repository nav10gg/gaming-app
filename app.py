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
        
        # Open the specific sheet and tab
        sheet = client.open("My Squad Tracker").worksheet("Ranked Resurgence") 
        
        raw_data = sheet.get_all_values()
        
        if not raw_data:
             return pd.DataFrame()
             
        # Tell Pandas to use the first row as headers, and the rest as data
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        
        # List the EXACT names of the columns you want to show in the app
        columns_to_keep = [
            "Total Score", "P1 Name", "P1 Kills", 
            "P2 Name", "P2 Kills", "P3 Name", 
            "P3 Kills", "P4 Names", "P4 Kills"
        ] 
        
        # This safety check ensures the app doesn't crash if a column name is misspelled
        safe_columns = [col for col in columns_to_keep if col in df.columns]
        
        # Slice the dataframe down to just those specific columns
        df = df[safe_columns]
        
        # Automatically sort the leaderboard by Total Score (highest at the top)
        if "Total Score" in df.columns:
            # Convert to numbers so it sorts mathematically, not alphabetically
            df["Total Score"] = pd.to_numeric(df["Total Score"], errors="coerce")
            df = df.sort_values(by="Total Score", ascending=False)
        
        return df

    except Exception as e:
        # This catches any errors and prevents the app from crashing
        st.error(f"Failed to connect to Google Sheets: {e}")
        return pd.DataFrame()

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
st.write("Match submission form coming soon...")
