import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Set page config
st.set_page_config(page_title="Time Audit Tracker", layout="wide")

# Google Sheets setup
@st.cache_resource
def get_gsheet_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    
    return gspread.authorize(credentials)

# Load data from Google Sheets
@st.cache_data(ttl=10)
def load_data():
    try:
        client = get_gsheet_client()
        sheet = client.open("Time Audit Data").sheet1
        
        data = sheet.get_all_records()
        if len(data) == 0:
            # Initialize with headers
            headers = [
                "Date", "Time", "Activity", "Happiness Rating", "Notes",
                "Day Weather", "Day Breakfast", "Day Lunch", "Day Dinner", "Exercise?"
            ]
            sheet.append_row(headers)
            return pd.DataFrame(columns=headers)
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(columns=[
            "Date", "Time", "Activity", "Happiness Rating", "Notes",
            "Day Weather", "Day Breakfast", "Day Lunch", "Day Dinner", "Exercise?"
        ])

# Save data to Google Sheets
def save_data(df):
    try:
        client = get_gsheet_client()
        sheet = client.open("Time Audit Data").sheet1
        
        # Clear existing data
        sheet.clear()
        
        # Write headers and data
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        
        # Clear cache so new data loads
        st.cache_data.clear()
        
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# Generate time slots (30-minute intervals)
def generate_time_slots():
    slots = []
    current = datetime.strptime("00:00", "%H:%M")
    end = datetime.strptime("23:30", "%H:%M")
    
    while current <= end:
        slots.append(current.strftime("%I:%M %p"))
        current += timedelta(minutes=30)
    
    return slots

# Main app
def main():
    st.title("⏰ Time Audit Tracker")
    
    # Load existing data
    df = load_data()
    
    # Sidebar for navigation
    st.sidebar.header("Navigation")
    mode = st.sidebar.radio("Choose Mode", ["Log Entry", "View Data", "Edit Day Info"])
    
    if mode == "Log Entry":
        st.header("📝 Log Time Entry")
        
        col1, col2 = st.columns(2)
        
        with col1:
            entry_date = st.date_input("Date", value=date.today())
        
        with col2:
            time_slots = generate_time_slots()
            entry_time = st.selectbox("Time Slot", time_slots)
        
        entry_activity = st.text_input("Activity", placeholder="What were you doing?")
        
        entry_happiness = st.slider("Happiness Rating", 1, 10, 5)
        
        entry_notes = st.text_area("Notes", placeholder="Any additional thoughts?")
        
        # Day-level information
        existing_day_entries = df[df["Date"] == str(entry_date)]
        
        if len(existing_day_entries) == 0:
            st.subheader("📅 Daily Information")
            st.info("This is the first entry for this day. Please fill in the daily information.")
            
            col3, col4 = st.columns(2)
            
            with col3:
                day_weather = st.text_input("Weather", placeholder="Sunny, rainy, cloudy...")
                day_breakfast = st.text_input("Breakfast", placeholder="What did you eat?")
            
            with col4:
                day_lunch = st.text_input("Lunch", placeholder="What did you eat?")
                day_dinner = st.text_input("Dinner", placeholder="What did you eat?")
            
            day_exercise = st.radio("Exercise?", ["Yes", "No"])
        else:
            # Use existing day info
            day_weather = existing_day_entries.iloc[0]["Day Weather"]
            day_breakfast = existing_day_entries.iloc[0]["Day Breakfast"]
            day_lunch = existing_day_entries.iloc[0]["Day Lunch"]
            day_dinner = existing_day_entries.iloc[0]["Day Dinner"]
            day_exercise = existing_day_entries.iloc[0]["Exercise?"]
            
            st.info(f"Using existing day info: Weather: {day_weather}, Exercise: {day_exercise}")
        
        if st.button("💾 Save Entry", type="primary"):
            if entry_activity:
                new_entry = {
                    "Date": str(entry_date),
                    "Time": entry_time,
                    "Activity": entry_activity,
                    "Happiness Rating": entry_happiness,
                    "Notes": entry_notes,
                    "Day Weather": day_weather,
                    "Day Breakfast": day_breakfast,
                    "Day Lunch": day_lunch,
                    "Day Dinner": day_dinner,
                    "Exercise?": day_exercise
                }
                
                # Check if entry already exists
                existing_entry = df[(df["Date"] == str(entry_date)) & (df["Time"] == entry_time)]
                
                if len(existing_entry) > 0:
                    # Update existing entry
                    df.loc[(df["Date"] == str(entry_date)) & (df["Time"] == entry_time), :] = list(new_entry.values())
                    message = f"✅ Updated entry for {entry_date} at {entry_time}"
                else:
                    # Add new entry
                    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                    message = f"✅ Saved entry for {entry_date} at {entry_time}"
                
                if save_data(df):
                    st.success(message)
                    st.rerun()
            else:
                st.error("⚠️ Please enter an activity!")
    
    elif mode == "View Data":
        st.header("📊 View Your Data")
        
        if len(df) == 0:
            st.info("No data yet! Start logging entries.")
        else:
            # Filter options
            col1, col2 = st.columns(2)
            
            with col1:
                dates = sorted(df["Date"].unique(), reverse=True)
                filter_date = st.selectbox("Filter by Date", ["All"] + list(dates))
            
            with col2:
                sort_by = st.selectbox("Sort by", ["Date", "Happiness Rating"])
            
            # Filter data
            if filter_date != "All":
                filtered_df = df[df["Date"] == filter_date]
            else:
                filtered_df = df.copy()
            
            # Sort data
            if sort_by == "Happiness Rating":
                filtered_df = filtered_df.sort_values("Happiness Rating", ascending=False)
            else:
                filtered_df = filtered_df.sort_values(["Date", "Time"])
            
            # Display data
            st.dataframe(filtered_df, use_container_width=True)
            
            # Summary statistics
            st.subheader("📈 Summary Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_happiness = filtered_df["Happiness Rating"].mean()
                st.metric("Average Happiness", f"{avg_happiness:.1f}/10")
            
            with col2:
                total_entries = len(filtered_df)
                st.metric("Total Entries", total_entries)
            
            with col3:
                if filter_date != "All":
                    exercise_status = filtered_df.iloc[0]["Exercise?"] if len(filtered_df) > 0 else "N/A"
                    st.metric("Exercise", exercise_status)
            
            # Download button
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Data as CSV",
                data=csv,
                file_name=f"time_audit_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    elif mode == "Edit Day Info":
        st.header("✏️ Edit Daily Information")
        
        if len(df) == 0:
            st.info("No data yet! Start logging entries.")
        else:
            dates = sorted(df["Date"].unique(), reverse=True)
            selected_date = st.selectbox("Select Date", dates)
            
            day_entries = df[df["Date"] == selected_date]
            
            if len(day_entries) > 0:
                current_weather = day_entries.iloc[0]["Day Weather"]
                current_breakfast = day_entries.iloc[0]["Day Breakfast"]
                current_lunch = day_entries.iloc[0]["Day Lunch"]
                current_dinner = day_entries.iloc[0]["Day Dinner"]
                current_exercise = day_entries.iloc[0]["Exercise?"]
                
                st.subheader(f"Current Info for {selected_date}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    new_weather = st.text_input("Weather", value=current_weather)
                    new_breakfast = st.text_input("Breakfast", value=current_breakfast)
                
                with col2:
                    new_lunch = st.text_input("Lunch", value=current_lunch)
                    new_dinner = st.text_input("Dinner", value=current_dinner)
                
                new_exercise = st.radio("Exercise?", ["Yes", "No"], 
                                       index=0 if current_exercise == "Yes" else 1)
                
                if st.button("💾 Update Day Info", type="primary"):
                    df.loc[df["Date"] == selected_date, "Day Weather"] = new_weather
                    df.loc[df["Date"] == selected_date, "Day Breakfast"] = new_breakfast
                    df.loc[df["Date"] == selected_date, "Day Lunch"] = new_lunch
                    df.loc[df["Date"] == selected_date, "Day Dinner"] = new_dinner
                    df.loc[df["Date"] == selected_date, "Exercise?"] = new_exercise
                    
                    if save_data(df):
                        st.success(f"✅ Updated daily info for {selected_date}")
                        st.rerun()

if __name__ == "__main__":
    main()
