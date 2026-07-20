import streamlit as st
import datetime
import sqlite3
import pandas as pd

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('family_fitness.db', check_same_thread=False)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    # Challenges table
    c.execute('''CREATE TABLE IF NOT EXISTS challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    challenge_num INTEGER,
                    goal_type TEXT, 
                    goal_desc TEXT,
                    target_val REAL,
                    start_val REAL,
                    weekly_target_days INTEGER,
                    created_at TEXT)''')
    # Daily Logs table
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
                    username TEXT,
                    challenge_num INTEGER,
                    date TEXT,
                    status TEXT, -- 'completed', 'skipped', 'failed'
                    current_numeric_val REAL,
                    PRIMARY KEY (username, challenge_num, date))''')
    conn.commit()
    return conn

conn = init_db()

# --- HELPER FUNCTIONS ---
def get_current_week_range():
    today = datetime.date.today()
    idx = (today.weekday() + 1) % 7 
    sun = today - datetime.timedelta(days=idx)
    sat = sun + datetime.timedelta(days=6)
    return sun, sat

def is_editable(created_at_str):
    if not created_at_str:
        return True
    created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    return (datetime.datetime.now() - created_at).total_seconds() < 86400

# --- APP CONFIG & STYLING ---
st.set_page_config(page_title="Family Fitness Challenge", page_icon="💪", layout="centered")

# Flat CSS string to absolutely avoid python indentation bugs
st.markdown("<style>.stButton>button { width: 100%; border-radius: 10px; } .highlight-box { background-color: #f0f7f4; padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32; }</style>", unsafe_allow_html=True)

# Define current week variables globally at the top level so all blocks can access them safely
sun, sat = get_current_week_range()

# --- AUTHENTICATION STATE ---
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.current_tab = "🏆 Leaderboard"

# --- AUTH INTERFACE ---
if st.session_state.user is None:
    st.title("💪 Family 6-Week Fitness Challenge")
    auth_mode = st.radio("Choose Action", ["Login", "Sign Up"])
    username = st.text_input("Username").strip().lower()
    password = st.text_input("Password", type="password")
    
    if st.button(auth_mode):
        c = conn.cursor()
        if auth_mode == "Sign Up":
            try:
                c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
                conn.commit()
                st.session_state.user = username
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Username already exists!")
        else:
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            if c.fetchone():
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Invalid credentials.")
    st.stop()

# --- LOGGED IN APP INTERFACE ---
st.title(f"🏆 Family Challenge")
st.caption(f"Logged in as: **{st.session_state.user.capitalize()}**")

# Bottom Navigation Emulation via Columns
col1, col2, col3, col4 = st.columns(4)
with col1: 
    if st.button("🏆 Board"): st.session_state.current_tab = "🏆 Leaderboard"
with col2: 
    if st.button("📝 Log"): st.session_state.current_tab = "📝 Daily Log"
with col3: 
    if st.button("⚙️ Setup"): st.session_state.current_tab = "⚙️ Setup"
with col4: 
    if st.button("📊 Stats"): st.session_state.current_tab = "📊 Stats"

st.divider()

# --- TAB 1: LEADERBOARD ---
if st.session_state.current_tab == "🏆 Leaderboard":
    st.subheader("Family Progress Dashboard")
    st.markdown(f"<div class='highlight-box'>📅 <b>Current Week:</b> {sun.strftime('%b %d')} to {sat.strftime('%b %d')} (Resets Sunday)</div>", unsafe_allow_html=True)
    st.write("")
    
    c = conn.cursor()
    c.execute("SELECT username, challenge_num, goal_type, goal_desc, target_val, start_val, weekly_target_days FROM challenges")
    all_challenges = c.fetchall()
    
    if not all_challenges:
        st.info("Nobody has set up a challenge yet!")
    else:
        df = pd.DataFrame(all_challenges, columns=['User', 'Num', 'Type', 'Desc', 'Target', 'Start', 'WeeklyTarget'])
        
        for user in df['User'].unique():
            st.markdown(f"### 👤 {user.capitalize()}")
            user_challs = df[df['User'] == user]
            
            for _, row in user_challs.iterrows():
                st.write(f"**Challenge:** {row['Desc']}")
                
                # Fetch logs for current week
                c.execute("SELECT status FROM logs WHERE username=? AND challenge_num=? AND date BETWEEN ? AND ?", 
                          (user, row['Num'], sun.isoformat(), sat.isoformat()))
                week_logs = c.fetchall()
                completed_days_this_week = sum(1 for l in week_logs if l[0] == 'completed')
                
                # Fetch all-time logs for overall progress
                c.execute("SELECT status, current_numeric_val FROM logs WHERE username=? AND challenge_num=?", (user, row['Num']))
                all_logs = c.fetchall()
                
                if row['Type'] == "Weight / Numeric Goal":
                    if all_logs:
                        valid_vals = [l[1] for l in all_logs if l[1] is not None]
                        if valid_vals:
                            latest_val = valid_vals[-1]
                            total_change_needed = row['Target'] - row['Start']
                            current_change = latest_val - row['Start']
                            
                            if total_change_needed == 0:
                                progress_pct = 1.0
                            else:
                                progress_pct = min(max(current_change / total_change_needed, 0.0), 1.0)
                            
                            st.progress(progress_pct)
                            st.caption(f"Progress: {int(progress_pct * 100)}% of goal met")
                        else:
                            st.caption("No weight/numeric logs recorded yet.")
                    else:
                        st.caption("No progress recorded yet.")
                        
                elif row['Type'] == "Weekly Frequency Target":
                    st.write(f"Status this week: `{completed_days_this_week} / {row['WeeklyTarget']} days` completed")
                    pct = min(completed_days_this_week / row['WeeklyTarget'], 1.0) if row['WeeklyTarget'] > 0 else 0
                    st.progress(pct)
                    
                else: # Daily Habit
                    total_days_completed = sum(1 for l in all_logs if l[0] == 'completed')
                    st.write(f"Total successful days overall: `{total_days_completed} days` 🎉")
            st.divider()

# --- TAB 2: DAILY LOG ---
elif st.session_state.current_tab == "📝 Daily Log":
    st.subheader("Log Your Progress")
    log_date = st.date_input("Date to log for", datetime.date.today())
    
    c = conn.cursor()
    c.execute("SELECT challenge_num, goal_type, goal_desc FROM challenges WHERE username=?", (st.session_state.user,))
    my_challenges = c.fetchall()
    
    if not my_challenges:
        st.warning("Please set up your challenges first in the Setup tab!")
    else:
        with st.form("log_form"):
            for num, g_type, desc in my_challenges:
                st.markdown(f"#### Log for: *{desc}*")
                
                c.execute("SELECT status, current_numeric_val FROM logs WHERE username=? AND challenge_num=? AND date=?", 
                          (st.session_state.user, num, log_date.isoformat()))
                existing = c.fetchone()
                
                existing_status = existing[0] if existing else "failed"
                existing_num = existing[1] if existing else 0.0
                
                skip = st.checkbox("Exclude/Skip this day (Won't count against you)", value=(existing_status == 'skipped'), key=f"skip_{num}")
                
                if g_type == "Weight / Numeric Goal":
                    val = st.number_input("Current Value / Weight", value=float(existing_num) if existing_num else 0.0, key=f"val_{num}")
                else:
                    done = st.checkbox("I completed this goal today!", value=(existing_status == 'completed'), key=f"done_{num}")
                    
            if st.form_submit_button("Save Today's Logs"):
                for num, g_type, desc in my_challenges:
                    is_skipped = st.session_state[f"skip_{num}"]
                    
                    if is_skipped:
                        status = 'skipped'
                        num_val = None
                    elif g_type == "Weight / Numeric Goal":
                        status = 'completed'
                        num_val = st.session_state[f"val_{num}"]
                    else:
                        status = 'completed' if st.session_state[f"done_{num}"] else 'failed'
                        num_val = None
                        
                    c.execute('''INSERT OR REPLACE INTO logs (username, challenge_num, date, status, current_numeric_val) 
                                 VALUES (?, ?, ?, ?, ?)''', (st.session_state.user, num, log_date.isoformat(), status, num_val))
                conn.commit()
                st.success("Progress saved successfully!")

# --- TAB 3: CHALLENGE SETUP ---
elif st.session_state.current_tab == "⚙️ Setup":
    st.subheader("Setup Your 6-Week Challenges")
    st.info("💡 You can select up to 3 challenges. Note: Your challenge locks 24 hours after submission!")
    
    c = conn.cursor()
    c.execute("SELECT challenge_num, goal_type, goal_desc, target_val, start_val, weekly_target_days, created_at FROM challenges WHERE username=?", (st.session_state.user,))
    existing_challenges = c.fetchall()
    
    can_edit = True
    if existing_challenges and existing_challenges[0][6]:
        can_edit = is_editable(existing_challenges[0][6])
        if not can_edit:
            st.error("🔒 Your 24-hour editing window has closed. Challenges are now locked!")
            
    presets = ["Lose/Maintain Weight", "No Sugar", "10,000 Steps per day", "Exercise 3x a week", "Log food daily", "Custom"]
    
    with st.form("challenge_setup_form"):
        num_challenges = st.slider("How many challenges do you want to set?", 1, 3, len(existing_challenges) if existing_challenges else 1, disabled=not can_edit)
        
        for i in range(1, num_challenges + 1):
            st.markdown(f"### 🎯 Challenge #{i}")
            
            ex = next((x for x in existing_challenges if x[0] == i), None)
            ex_type = ex[1] if ex else "Daily Habit (Yes/No)"
            ex_desc = ex[2] if ex else ""
            ex_target = ex[3] if ex else 0.0
            ex_start = ex[4] if ex else 0.0
            ex_weekly = ex[5] if ex else 3
            
            goal_type = st.selectbox("Goal Tracking Style", ["Daily Habit (Yes/No)", "Weekly Frequency Target", "Weight / Numeric Goal"], index=["Daily Habit (Yes/No)", "Weekly Frequency Target", "Weight / Numeric Goal"].index(ex_type), key=f"type_{i}", disabled=not can_edit)
            preset_choice = st.selectbox("Quick Recommendations", presets, key=f"preset_{i}", disabled=not can_edit)
            custom_desc = st.text_input("Challenge Name / Description", value=ex_desc if ex_desc else (preset_choice if preset_choice != "Custom" else ""), key=f"desc_{i}", disabled=not can_edit)
            
            if goal_type == "Weight / Numeric Goal":
                c_start = st.number_input("Starting Weight/Value (Private)", value=float(ex_start), key=f"start_{i}", disabled=not can_edit)
                c_target = st.number_input("Target Weight/Value (Private)", value=float(ex_target), key=f"target_{i}", disabled=not can_edit)
            elif goal_type == "Weekly Frequency Target":
                c_weekly = st.number_input("Target days per week", min_value=1, max_value=7, value=int(ex_weekly), key=f"weekly_{i}", disabled=not can_edit)
                
        submit = st.form_submit_button("Lock in Challenges", disabled=not can_edit)
        
        if submit and can_edit:
            c.execute("DELETE FROM challenges WHERE username=?", (st.session_state.user,))
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for i in range(1, num_challenges + 1):
                g_type = st.session_state[f"type_{i}"]
                desc = st.session_state[f"desc_{i}"]
                t_val = st.session_state[f"target_{i}"] if g_type == "Weight / Numeric Goal" else 0
                s_val = st.session_state[f"start_{i}"] if g_type == "Weight / Numeric Goal" else 0
                w_target = st.session_state[f"weekly_{i}"] if g_type == "Weekly Frequency Target" else 0
                
                c.execute('''INSERT INTO challenges (username, challenge_num, goal_type, goal_desc, target_val, start_val, weekly_target_days, created_at) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (st.session_state.user, i, g_type, desc, t_val, s_val, w_target, timestamp))
            conn.commit()
            st.success("Challenges saved! You have 24 hours to change them.")
            st.rerun()

# --- TAB 4: STATS & HISTORICAL WINNERS ---
elif st.session_state.current_tab == "📊 Stats":
    st.subheader("Challenge Performance History")
    
    c = conn.cursor()
    c.execute("""SELECT username, COUNT(CASE WHEN status='completed' THEN 1 END) as completed_days 
                 FROM logs GROUP BY username ORDER BY completed_days DESC""")
    leaderboard_data = c.fetchall()
    
    if not leaderboard_data:
        st.info("No historical data to display yet.")
    else:
        st.markdown("### 🏅 Current Standings (Total Days Completed)")
        for rank, (user, total) in enumerate(leaderboard_data, 1):
            st.write(f"**#{rank} {user.capitalize()}** — {total} total metrics accomplished!")
st.set_page_config(page_title="Family Fitness Challenge", page_icon="💪", layout="centered")

# Custom CSS for Mobile App-like Bottom Navigation
st.markdown("<style>.stButton>button { width: 100%; border-radius: 10px; } .highlight-box { background-color: #f0f7f4; padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32; }</style>", unsafe_allow_html=True)

# Instead of:
# st.markdown(f"<div class='highlight-box'>📅 <b>Current Week:</b> {sun.strftime('%b %d')} to {sat.strftime('%b %d')} (Resets Sunday)</div>", unsafe_allow_html=True)

st.markdown(f"📅 **Current Week:** {sun.strftime('%b %d')} to {sat.strftime('%b %d')} (Resets Sunday)")

# Or if you need custom styling:
from markupsafe import escape
safe_username = escape(user)
st.markdown(f"<div class='highlight-box'>{safe_username}</div>", unsafe_allow_html=True)

# --- AUTHENTICATION STATE ---
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.current_tab = "🏆 Leaderboard"

# --- HELPER FUNCTIONS ---
def get_current_week_range():
    today = datetime.date.today()
    # Sunday rollover logic (idx 6 is Sunday in some systems, let's calculate based on Sunday = day 0)
    idx = (today.weekday() + 1) % 7 
    sun = today - datetime.timedelta(days=idx)
    sat = sun + datetime.timedelta(days=6)
    return sun, sat

def is_editable(created_at_str):
    if not created_at_str:
        return True
    created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    return (datetime.datetime.now() - created_at).total_seconds() < 86400

# --- AUTH INTERFACE ---
if st.session_state.user is None:
    st.title("💪 Family 6-Week Fitness Challenge")
    auth_mode = st.radio("Choose Action", ["Login", "Sign Up"])
    username = st.text_input("Username").strip().lower()
    password = st.text_input("Password", type="password")
    
    if st.button(auth_mode):
        c = conn.cursor()
        if auth_mode == "Sign Up":
            try:
                c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
                conn.commit()
                st.session_state.user = username
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Username already exists!")
        else:
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            if c.fetchone():
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Invalid credentials.")
    st.stop()

# --- LOGGED IN APP INTERFACE ---
st.title(f"🏆 Family Challenge")
st.caption(f"Logged in as: **{st.session_state.user.capitalize()}**")

# Calculate current week variables right away so the whole app can use them
sun, sat = get_current_week_range()

# Bottom Navigation Emulation via Columns
col1, col2, col3, col4 = st.columns(4)
with col1: 
    if st.button("🏆 Board"): st.session_state.current_tab = "🏆 Leaderboard"
with col2: 
    if st.button("📝 Log"): st.session_state.current_tab = "📝 Daily Log"
with col3: 
    if st.button("⚙️ Setup"): st.session_state.current_tab = "⚙️ Setup"
with col4: 
    if st.button("📊 Stats"): st.session_state.current_tab = "📊 Stats"

st.divider()

# --- TAB 1: LEADERBOARD ---
if st.session_state.current_tab == "🏆 Leaderboard":
    st.subheader("Family Progress Dashboard")
    st.markdown(f"<div class='highlight-box'>📅 <b>Current Week:</b> {sun.strftime('%b %d')} to {sat.strftime('%b %d')} (Resets Sunday)</div>", unsafe_allow_html=True)
    st.write("")

st.divider()

# --- TAB 1: LEADERBOARD ---
if st.session_state.current_tab == "🏆 Leaderboard":
    st.subheader("Family Progress Dashboard")
    sun, sat = get_current_week_range()
    st.markdown(f"<div class='highlight-box'>📅 <b>Current Week:</b> {sun.strftime('%b %d')} to {sat.strftime('%b %d')} (Resets Sunday)</div>", unsafe_allow_html=True)
    st.write("")
    
    c = conn.cursor()
    c.execute("SELECT username, challenge_num, goal_type, goal_desc, target_val, start_val, weekly_target_days FROM challenges")
    all_challenges = c.fetchall()
    
    if not all_challenges:
        st.info("Nobody has set up a challenge yet!")
    else:
        # Group by user for clean display
        df = pd.DataFrame(all_challenges, columns=['User', 'Num', 'Type', 'Desc', 'Target', 'Start', 'WeeklyTarget'])
        
        for user in df['User'].unique():
            st.markdown(f"### 👤 {user.capitalize()}")
            user_challs = df[df['User'] == user]
            
            for _, row in user_challs.iterrows():
                st.write(f"**Challenge:** {row['Desc']}")
                
                # Fetch logs for current week
                c.execute("SELECT status FROM logs WHERE username=? AND challenge_num=? AND date BETWEEN ? AND ?", 
                          (user, row['Num'], sun.isoformat(), sat.isoformat()))
                week_logs = c.fetchall()
                completed_days_this_week = sum(1 for l in week_logs if l[0] == 'completed')
                
                # Fetch all-time logs for overall progress
                c.execute("SELECT status, current_numeric_val FROM logs WHERE username=? AND challenge_num=?", (user, row['Num']))
                all_logs = c.fetchall()
                
                if row['Type'] == "Weight / Numeric Goal":
                    # Masking the real numbers, only show percentage completion
                    if all_logs:
                        # Get latest logged numeric value
                        valid_vals = [l[1] for l in all_logs if l[1] is not None]
                        if valid_vals:
                            latest_val = valid_vals[-1]
                            total_change_needed = row['Target'] - row['Start']
                            current_change = latest_val - row['Start']
                            
                            if total_change_needed == 0:
                                progress_pct = 1.0
                            else:
                                progress_pct = min(max(current_change / total_change_needed, 0.0), 1.0)
                            
                            st.progress(progress_pct)
                            st.caption(f"Progress: {int(progress_pct * 100)}% of goal met")
                        else:
                            st.caption("No weight/numeric logs recorded yet.")
                    else:
                        st.caption("No progress recorded yet.")
                        
                elif row['Type'] == "Weekly Frequency Target":
                    st.write(f"Status this week: `{completed_days_this_week} / {row['WeeklyTarget']} days` completed")
                    pct = min(completed_days_this_week / row['WeeklyTarget'], 1.0) if row['WeeklyTarget'] > 0 else 0
                    st.progress(pct)
                    
                else: # Daily Habit (No sugar, 10k steps, etc)
                    total_days_completed = sum(1 for l in all_logs if l[0] == 'completed')
                    st.write(f"Total successful days overall: `{total_days_completed} days` 🎉")
            st.divider()

# --- TAB 2: DAILY LOG ---
elif st.session_state.current_tab == "📝 Daily Log":
    st.subheader("Log Your Progress")
    log_date = st.date_input("Date to log for", datetime.date.today())
    
    c = conn.cursor()
    c.execute("SELECT challenge_num, goal_type, goal_desc FROM challenges WHERE username=?", (st.session_state.user,))
    my_challenges = c.fetchall()
    
    if not my_challenges:
        st.warning("Please set up your challenges first in the Setup tab!")
    else:
        with st.form("log_form"):
            for num, g_type, desc in my_challenges:
                st.markdown(f"#### Log for: *{desc}*")
                
                # Check if existing log exists
                c.execute("SELECT status, current_numeric_val FROM logs WHERE username=? AND challenge_num=? AND date=?", 
                          (st.session_state.user, num, log_date.isoformat()))
                existing = c.fetchone()
                
                existing_status = existing[0] if existing else "failed"
                existing_num = existing[1] if existing else 0.0
                
                skip = st.checkbox("Exclude/Skip this day (Won't count against you)", value=(existing_status == 'skipped'), key=f"skip_{num}")
                
                if g_type == "Weight / Numeric Goal":
                    val = st.number_input("Current Value / Weight", value=float(existing_num) if existing_num else 0.0, key=f"val_{num}")
                else:
                    done = st.checkbox("I completed this goal today!", value=(existing_status == 'completed'), key=f"done_{num}")
                    
            if st.form_submit_button("Save Today's Logs"):
                for num, g_type, desc in my_challenges:
                    is_skipped = st.session_state[f"skip_{num}"]
                    
                    if is_skipped:
                        status = 'skipped'
                        num_val = None
                    elif g_type == "Weight / Numeric Goal":
                        status = 'completed'
                        num_val = st.session_state[f"val_{num}"]
                    else:
                        status = 'completed' if st.session_state[f"done_{num}"] else 'failed'
                        num_val = None
                        
                    c.execute('''INSERT OR REPLACE INTO logs (username, challenge_num, date, status, current_numeric_val) 
                                 VALUES (?, ?, ?, ?, ?)''', (st.session_state.user, num, log_date.isoformat(), status, num_val))
                conn.commit()
                st.success("Progress saved successfully!")

# --- TAB 3: CHALLENGE SETUP ---
elif st.session_state.current_tab == "⚙️ Setup":
    st.subheader("Setup Your 6-Week Challenges")
    st.info("💡 You can select up to 3 challenges. Note: Your challenge locks 24 hours after submission!")
    
    c = conn.cursor()
    c.execute("SELECT challenge_num, goal_type, goal_desc, target_val, start_val, weekly_target_days, created_at FROM challenges WHERE username=?", (st.session_state.user,))
    existing_challenges = c.fetchall()
    
    can_edit = True
    if existing_challenges and existing_challenges[0][6]:
        can_edit = is_editable(existing_challenges[0][6])
        if not can_edit:
            st.error("🔒 Your 24-hour editing window has closed. Challenges are now locked!")
            
    presets = ["Lose/Maintain Weight", "No Sugar", "10,000 Steps per day", "Exercise 3x a week", "Log food daily", "Custom"]
    
    with st.form("challenge_setup_form"):
        num_challenges = st.slider("How many challenges do you want to set?", 1, 3, len(existing_challenges) if existing_challenges else 1, disabled=not can_edit)
        
        for i in range(1, num_challenges + 1):
            st.markdown(f"### 🎯 Challenge #{i}")
            
            # Find existing data if available
            ex = next((x for x in existing_challenges if x[0] == i), None)
            
            ex_type = ex[1] if ex else "Daily Habit (Yes/No)"
            ex_desc = ex[2] if ex else ""
            ex_target = ex[3] if ex else 0.0
            ex_start = ex[4] if ex else 0.0
            ex_weekly = ex[5] if ex else 3
            
            goal_type = st.selectbox("Goal Tracking Style", ["Daily Habit (Yes/No)", "Weekly Frequency Target", "Weight / Numeric Goal"], index=["Daily Habit (Yes/No)", "Weekly Frequency Target", "Weight / Numeric Goal"].index(ex_type), key=f"type_{i}", disabled=not can_edit)
            
            preset_choice = st.selectbox("Quick Recommendations", presets, key=f"preset_{i}", disabled=not can_edit)
            
            custom_desc = st.text_input("Challenge Name / Description", value=ex_desc if ex_desc else (preset_choice if preset_choice != "Custom" else ""), key=f"desc_{i}", disabled=not can_edit)
            
            if goal_type == "Weight / Numeric Goal":
                c_start = st.number_input("Starting Weight/Value (Private)", value=float(ex_start), key=f"start_{i}", disabled=not can_edit)
                c_target = st.number_input("Target Weight/Value (Private)", value=float(ex_target), key=f"target_{i}", disabled=not can_edit)
            elif goal_type == "Weekly Frequency Target":
                c_weekly = st.number_input("Target days per week", min_value=1, max_value=7, value=int(ex_weekly), key=f"weekly_{i}", disabled=not can_edit)
                
        submit = st.form_submit_button("Lock in Challenges", disabled=not can_edit)
        
        if submit and can_edit:
            # Clear old entries for user to rewrite safely
            c.execute("DELETE FROM challenges WHERE username=?", (st.session_state.user,))
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for i in range(1, num_challenges + 1):
                g_type = st.session_state[f"type_{i}"]
                desc = st.session_state[f"desc_{i}"]
                t_val = st.session_state[f"target_{i}"] if g_type == "Weight / Numeric Goal" else 0
                s_val = st.session_state[f"start_{i}"] if g_type == "Weight / Numeric Goal" else 0
                w_target = st.session_state[f"weekly_{i}"] if g_type == "Weekly Frequency Target" else 0
                
                c.execute('''INSERT INTO challenges (username, challenge_num, goal_type, goal_desc, target_val, start_val, weekly_target_days, created_at) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (st.session_state.user, i, g_type, desc, t_val, s_val, w_target, timestamp))
            conn.commit()
            st.success("Challenges saved! You have 24 hours to change them.")
            st.rerun()

# --- TAB 4: STATS & HISTORICAL WINNERS ---
elif st.session_state.current_tab == "📊 Stats":
    st.subheader("Challenge Performance History")
    
    c = conn.cursor()
    c.execute("""SELECT username, COUNT(CASE WHEN status='completed' THEN 1 END) as completed_days 
                 FROM logs GROUP BY username ORDER BY completed_days DESC""")
    leaderboard_data = c.fetchall()
    
    if not leaderboard_data:
        st.info("No historical data to display yet.")
    else:
        st.markdown("### 🏅 Current Standings (Total Days Completed)")
        for rank, (user, total) in enumerate(leaderboard_data, 1):
            st.write(f"**#{rank} {user.capitalize()}** — {total} total metrics accomplished!")
