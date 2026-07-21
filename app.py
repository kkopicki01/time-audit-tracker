import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import gspread
from google.oauth2.service_account import Credentials
import hashlib

# Set page config
st.set_page_config(page_title="Time Audit Tracker", layout="wide")

# User credentials - add your users here
USERS = {
    "kaylie": "bubbles",  # Change these!
    "dustin": "gunston"
}

# Hash password for security
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Check login
def check_login(username, password):
    if username in USERS and USERS[username] == password:
        return True
    return False

# Login page
def login_page():
    st.title("🔐 Time Audit Tracker - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")

# Logout function
def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.rerun()

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

# Get or create user's spreadsheet
def get_user_spreadsheet(username):
    try:
        client = get_gsheet_client()
        spreadsheet_name = f"Time Audit Data - {username}"
        
        try:
            # Try to open existing spreadsheet
            spreadsheet = client.open(spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet if it doesn't exist
            spreadsheet = client.create(spreadsheet_name)
        
        return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Error accessing spreadsheet: {e}")
        return None

# Load data from Google Sheets
def load_data(username):
    try:
        sheet = get_user_spreadsheet(username)
        
        if sheet is None:
            return pd.DataFrame(columns=[
                "Date", "Time", "Activity", "Happiness Rating", "Notes",
                "Day Weather", "Day Breakfast", "Day Lunch", "Day Dinner", "Exercise?"
            ])
        
        data = sheet.get_all_records()
        if len(data) == 0:
            # Initialize with headers
            headers = [
                "Date", "Time", "Activity", "Happiness Rating", "Notes",
                "Day Weather", "Day Breakfast", "Day Lunch", "Day Dinner", "Exercise?"
            ]
            sheet.append_row(headers)
            return pd.DataFrame(columns=headers)
        
        df = pd.DataFrame(data)
        
        # Convert Happiness Rating to numeric (fixes the string issue)
        df["Happiness Rating"] = pd.to_numeric(df["Happiness Rating"], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(columns=[
            "Date", "Time", "Activity", "Happiness Rating", "Notes",
            "Day Weather", "Day Breakfast", "Day Lunch", "Day Dinner", "Exercise?"
        ])

# Save data to Google Sheets
def save_data(df, username):
    try:
        sheet = get_user_spreadsheet(username)
        
        if sheet is None:
            return False
        
        # Clear existing data
        sheet.clear()
        
        # Write headers and data
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        
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

# Generate sleep time slots between start and end time, handling date changes
def generate_sleep_slots_with_dates(sleep_start, sleep_end, wake_date):
    """Generate all 30-min slots between sleep start and end times with correct dates"""
    slots = []
    
    # Parse times
    start_time = datetime.strptime(sleep_start, "%I:%M %p")
    end_time = datetime.strptime(sleep_end, "%I:%M %p")
    
    # Wake date is the date selected by user
    wake_datetime = datetime.combine(wake_date, end_time.time())
    
    # If end time is before or equal to start time, sleep crossed midnight
    if end_time.time() <= start_time.time():
        # Sleep started the previous day
        sleep_datetime = wake_datetime - timedelta(days=1)
        sleep_datetime = sleep_datetime.replace(hour=start_time.hour, minute=start_time.minute)
    else:
        # Sleep started same day (nap)
        sleep_datetime = wake_datetime.replace(hour=start_time.hour, minute=start_time.minute)
    
    current = sleep_datetime
    while current < wake_datetime:
        slot_date = current.date()
        slot_time = current.strftime("%I:%M %p")
        slots.append((str(slot_date), slot_time))
        current += timedelta(minutes=30)
    
    return slots

# Sleep entry form
def sleep_entry_form(df, entry_date, username):
    st.header("😴 First, let's log your sleep!")
    st.info(f"Logging sleep for the night ending on {entry_date.strftime('%B %d, %Y')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        time_slots = generate_time_slots()
        sleep_start = st.selectbox("What time did you go to sleep?", time_slots, 
                                   index=time_slots.index("10:30 PM") if "10:30 PM" in time_slots else 0)
    
    with col2:
        sleep_end = st.selectbox("What time did you wake up?", time_slots,
                                 index=time_slots.index("06:30 AM") if "06:30 AM" in time_slots else 0)
    
    sleep_rating = st.slider("How would you rate your sleep quality?", 1, 10, 7)
    
    sleep_notes = st.text_area("Sleep notes (optional)", 
                               placeholder="Any dreams? Sleep disturbances? How do you feel?")
    
    # Show preview of time slots that will be filled
    preview_slots = generate_sleep_slots_with_dates(sleep_start, sleep_end, entry_date)
    
    # Determine if sleep crossed midnight
    start_time = datetime.strptime(sleep_start, "%I:%M %p")
    end_time = datetime.strptime(sleep_end, "%I:%M %p")
    crossed_midnight = end_time.time() <= start_time.time()
    
    if crossed_midnight:
        prev_date = entry_date - timedelta(days=1)
        st.info(f"✨ This will fill {len(preview_slots)} time slots from {sleep_start} on **{prev_date.strftime('%b %d')}** to {sleep_end} on **{entry_date.strftime('%b %d')}**")
    else:
        st.info(f"This will fill {len(preview_slots)} time slots from {sleep_start} to {sleep_end} on **{entry_date.strftime('%b %d')}** (same day - nap?)")
    
    # Daily info section - this should be for the WAKE UP date
    st.subheader(f"📅 Daily Information for {entry_date.strftime('%B %d, %Y')}")
    
    # Check if there's already daily info for the wake date
    existing_wake_entries = df[df["Date"] == str(entry_date)]
    
    if len(existing_wake_entries) > 0:
        day_weather = existing_wake_entries.iloc[0]["Day Weather"]
        day_breakfast = existing_wake_entries.iloc[0]["Day Breakfast"]
        day_lunch = existing_wake_entries.iloc[0]["Day Lunch"]
        day_dinner = existing_wake_entries.iloc[0]["Day Dinner"]
        day_exercise = existing_wake_entries.iloc[0]["Exercise?"]
        
        st.info(f"Using existing day info for {entry_date}: Weather: {day_weather}, Exercise: {day_exercise}")
    else:
        col3, col4 = st.columns(2)
        
        with col3:
            day_weather = st.text_input("Weather", placeholder="Sunny, rainy, cloudy...")
            day_breakfast = st.text_input("Breakfast", placeholder="What did you eat?")
        
        with col4:
            day_lunch = st.text_input("Lunch", placeholder="What did you eat?")
            day_dinner = st.text_input("Dinner", placeholder="What did you eat?")
        
        day_exercise = st.radio("Exercise?", ["Yes", "No"])
    
    if st.button("💾 Save Sleep Entry", type="primary"):
        # Generate all sleep time slots with correct dates
        sleep_slots = generate_sleep_slots_with_dates(sleep_start, sleep_end, entry_date)
        
        # Create entries for each sleep slot
        new_entries = []
        for slot_date, slot_time in sleep_slots:
            # Get daily info for this date
            # Sleep slots on previous day don't need full daily info
            existing_entries = df[df["Date"] == slot_date]
            
            if len(existing_entries) > 0:
                # Use existing daily info
                slot_weather = existing_entries.iloc[0]["Day Weather"]
                slot_breakfast = existing_entries.iloc[0]["Day Breakfast"]
                slot_lunch = existing_entries.iloc[0]["Day Lunch"]
                slot_dinner = existing_entries.iloc[0]["Day Dinner"]
                slot_exercise = existing_entries.iloc[0]["Exercise?"]
            elif slot_date == str(entry_date):
                # This is the wake date, use the info we collected
                slot_weather = day_weather
                slot_breakfast = day_breakfast
                slot_lunch = day_lunch
                slot_dinner = day_dinner
                slot_exercise = day_exercise
            else:
                # Previous day - use empty/placeholder values
                slot_weather = ""
                slot_breakfast = ""
                slot_lunch = ""
                slot_dinner = ""
                slot_exercise = ""
            
            new_entry = {
                "Date": slot_date,
                "Time": slot_time,
                "Activity": "Sleep",
                "Happiness Rating": sleep_rating,
                "Notes": sleep_notes if sleep_notes else "",
                "Day Weather": slot_weather,
                "Day Breakfast": slot_breakfast,
                "Day Lunch": slot_lunch,
                "Day Dinner": slot_dinner,
                "Exercise?": slot_exercise
            }
            new_entries.append(new_entry)
        
        # Add all entries to dataframe
        new_df = pd.concat([df, pd.DataFrame(new_entries)], ignore_index=True)
        
        if save_data(new_df, username):
            st.success(f"✅ Saved {len(sleep_slots)} sleep entries from {sleep_start} to {sleep_end}")
            st.balloons()
            st.rerun()
        
    return True

# Check if we need to log sleep for today
def needs_sleep_entry(df, entry_date):
    """Check if there's already sleep data for this date"""
    day_entries = df[df["Date"] == str(entry_date)]
    
    if len(day_entries) == 0:
        return True
    
    # Check if any entry has "Sleep" or "Sleeping" as activity
    sleep_entries = day_entries[day_entries["Activity"].str.lower().str.contains("sleep", na=False)]
    
    return len(sleep_entries) == 0

# Check if we need to log sleep for today
def needs_sleep_entry(df, entry_date):
    """Check if there's already sleep data ending on this date"""
    day_entries = df[df["Date"] == str(entry_date)]
    
    if len(day_entries) == 0:
        return True
    
    # Check if any entry has "Sleep" or "Sleeping" as activity
    sleep_entries = day_entries[day_entries["Activity"].str.lower().str.contains("sleep", na=False)]
    
    return len(sleep_entries) == 0

# Main app
def main():
    # Check if user is logged in
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
        return
    
    # User is logged in
    username = st.session_state.username
    
    st.title(f"⏰ Time Audit Tracker - Welcome {username.capitalize()}!")
    
    # Logout button in sidebar
    with st.sidebar:
        st.write(f"Logged in as: **{username}**")
        if st.button("🚪 Logout"):
            logout()
    
    # Load existing data for this user
    df = load_data(username)
    
    # Sidebar for navigation
    st.sidebar.header("Navigation")
    mode = st.sidebar.radio("Choose Mode", ["Log Entry", "Log Sleep", "View Data", "Edit Day Info"])
    
    if mode == "Log Entry":
        st.header("📝 Log Time Entry")
        
        col1, col2 = st.columns(2)
        
        with col1:
            entry_date = st.date_input("Date", value=date.today())
        
        # Check if we need sleep entry first
        if needs_sleep_entry(df, entry_date):
            st.warning("⚠️ You haven't logged your sleep for this day yet!")
            st.info("Please go to 'Log Sleep' in the sidebar first, or continue to log this activity.")
            
            if st.button("Go to Sleep Entry"):
                st.session_state.force_sleep_mode = True
                st.rerun()
        
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
                
                if save_data(df, username):
                    st.success(message)
                    st.rerun()
            else:
                st.error("⚠️ Please enter an activity!")
    
    elif mode == "Log Sleep":
        entry_date = st.date_input("Date", value=date.today())
        
        # Check if sleep already exists for this day
        if not needs_sleep_entry(df, entry_date):
            st.warning(f"You've already logged sleep for {entry_date}")
            if st.button("Re-enter sleep data (will overwrite)"):
                # Delete existing sleep entries for this date
                df = df[~((df["Date"] == str(entry_date)) & (df["Activity"].str.lower().str.contains("sleep", na=False)))]
        
        sleep_entry_form(df, entry_date, username)
    
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
            st.dataframe(filtered_df, width="stretch")
            
            # Summary statistics
            st.subheader("📈 Summary Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if len(filtered_df) > 0 and filtered_df["Happiness Rating"].notna().any():
                    avg_happiness = filtered_df["Happiness Rating"].mean()
                    st.metric("Average Happiness", f"{avg_happiness:.1f}/10")
                else:
                    st.metric("Average Happiness", "N/A")
            
            with col2:
                total_entries = len(filtered_df)
                st.metric("Total Entries", total_entries)
            
            with col3:
                sleep_entries = filtered_df[filtered_df["Activity"].str.lower().str.contains("sleep", na=False)]
                if len(sleep_entries) > 0 and sleep_entries["Happiness Rating"].notna().any():
                    avg_sleep_quality = sleep_entries["Happiness Rating"].mean()
                    st.metric("Avg Sleep Quality", f"{avg_sleep_quality:.1f}/10")
                else:
                    st.metric("Avg Sleep Quality", "N/A")
            
            with col4:
                if filter_date != "All" and len(filtered_df) > 0:
                    exercise_status = filtered_df.iloc[0]["Exercise?"] if len(filtered_df) > 0 else "N/A"
                    st.metric("Exercise", exercise_status)
                else:
                    st.metric("Exercise", "N/A")
            
            # Download button
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Data as CSV",
                data=csv,
                file_name=f"time_audit_{username}_{datetime.now().strftime('%Y%m%d')}.csv",
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
                    
                    if save_data(df, username):
                        st.success(f"✅ Updated daily info for {selected_date}")
                        st.rerun()

if __name__ == "__main__":
    main()
