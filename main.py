import psycopg2
import json
import os
import urllib.parse
import datetime

# Bypass the HTTPS requirement for local testing
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from fastapi import FastAPI, Form, Request, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from final_bot import parse_timetable

# --- CONFIGURATION ---
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_SECRETS_FILE = "web_credential.json"

# PASTE YOUR NEON CONNECTION STRING HERE
DATABASE_URL = os.getenv("DATABASE_URL")



# --- 1. DATABASE SETUP ---
def init_db():
    """Creates the PostgreSQL table if it doesn't exist yet."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # We create a table with Department, Level, and the actual JSON schedule
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS schedules
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       department
                       TEXT
                       NOT
                       NULL,
                       level
                       TEXT
                       NOT
                       NULL,
                       schedule_json
                       TEXT
                       NOT
                       NULL,
                       UNIQUE
                   (
                       department,
                       level
                   )
                       )
                   ''')
    conn.commit()
    cursor.close()
    conn.close()
    print("Cloud Database initialized successfully!")


# Run the database setup immediately
init_db()

# --- 2. FASTAPI SERVER SETUP ---
app = FastAPI(title="AFIT Timetable Hub")


@app.get("/", response_class=HTMLResponse)
def home():
    """This is the page students will see after paying on Selar."""

    # A simple HTML form for students to select their department and level
    html_content = """
    <html>
        <head>
            <title>AFIT Timetable Sync</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 50px; text-align: center; }
                select, button { padding: 10px; margin: 10px; font-size: 16px; }
                button { background-color: #4CAF50; color: white; border: none; cursor: pointer; }
            </style>
        </head>
        <body>
            <h2>Welcome to the AFIT Timetable Sync!</h2>
            <p>Select your department and level to get your calendar.</p>

            <form action="/sync" method="post">
                <select name="department" required>
                    <option value="" disabled selected>Select Department</option>

                    <optgroup label="Faculty of Air Engineering">
                        <option value="Aerospace Engineering">Aerospace Engineering</option>
                        <option value="Automotive Engineering">Automotive Engineering</option>
                        <option value="Mechanical Engineering">Mechanical Engineering</option>
                        <option value="Mechatronics Engineering">Mechatronics Engineering</option>
                        <option value="Metallurgical and Materials Engineering">Metallurgical and Materials Engineering</option>
                    </optgroup>

                    <optgroup label="Faculty of Ground & Communication Engineering">
                        <option value="Civil Engineering">Civil Engineering</option>
                        <option value="Electrical and Electronics Engineering">Electrical and Electronics Engineering</option>
                        <option value="Information and Communication Engineering">Information and Communication Technology</option>
                        <option value="Telecommunication Engineering">Telecommunication Engineering</option>
                    </optgroup>

                    <optgroup label="Faculty of Computing">
                        <option value="Computer Science">Computer Science</option>
                        <option value="Cyber Security">Cyber Security</option>
                    </optgroup>

                    <optgroup label="Faculty of Sciences">
                        <option value="Chemistry">Chemistry</option>
                        <option value="Mathematics">Mathematics</option>
                        <option value="Physics">Physics</option>
                        <option value="Physics with Electronics">Physics with Electronics</option>
                        <option value="Statistics">Statistics</option>
                    </optgroup>

                    <optgroup label="Faculty of Social & Management Sciences">
                        <option value="Accounting">Accounting</option>
                        <option value="Banking and Finance">Banking and Finance</option>
                        <option value="Business Administration">Business Administration</option>
                        <option value="Economics">Economics</option>
                        <option value="International Relations">International Relations</option>
                        <option value="Marketing">Marketing</option>
                    </optgroup>
                </select>
                <br>

                <select name="level" required>
                    <option value="" disabled selected>Select Level</option>
                    <option value="100">100 Level</option>
                    <option value="200">200 Level</option>
                    <option value="300">300 Level</option>
                    <option value="400">400 Level</option>
                    <option value="500">500 Level</option>
                </select>
                <br>

                <button type="submit">Generate My Calendar</button>
            </form>
        </body>
    </html>
    """
    return html_content


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    """The hidden page where Course Reps upload the PDFs."""
    return """
    <html>
        <head>
            <title>Course Rep Portal</title>
            <style>
                body { font-family: Arial; margin: 50px; text-align: center; }
                select, input, button { padding: 10px; margin: 10px; font-size: 16px; }
                button { background-color: #008CBA; color: white; border: none; cursor: pointer; }
            </style>
        </head>
        <body>
            <h2>Course Rep Upload Portal</h2>
            <p>Upload the official timetable PDF to the central database.</p>

            <form action="/admin/upload" method="post" enctype="multipart/form-data">
                <select name="department" required>
                    <option value="" disabled selected>Select Department</option>

                    <optgroup label="Faculty of Air Engineering">
                        <option value="Aerospace Engineering">Aerospace Engineering</option>
                        <option value="Automotive Engineering">Automotive Engineering</option>
                        <option value="Mechanical Engineering">Mechanical Engineering</option>
                        <option value="Mechatronics Engineering">Mechatronics Engineering</option>
                        <option value="Metallurgical and Materials Engineering">Metallurgical and Materials Engineering</option>
                    </optgroup>

                    <optgroup label="Faculty of Ground & Communication Engineering">
                        <option value="Civil Engineering">Civil Engineering</option>
                        <option value="Electrical and Electronics Engineering">Electrical and Electronics Engineering</option>
                        <option value="Information and Communication Engineering">Information and Communication Technology</option>
                        <option value="Telecommunication Engineering">Telecommunication Engineering</option>
                    </optgroup>

                    <optgroup label="Faculty of Computing">
                        <option value="Computer Science">Computer Science</option>
                        <option value="Cyber Security">Cyber Security</option>
                    </optgroup>

                    <optgroup label="Faculty of Sciences">
                        <option value="Chemistry">Chemistry</option>
                        <option value="Mathematics">Mathematics</option>
                        <option value="Physics">Physics</option>
                        <option value="Physics with Electronics">Physics with Electronics</option>
                        <option value="Statistics">Statistics</option>
                    </optgroup>

                    <optgroup label="Faculty of Social & Management Sciences">
                        <option value="Accounting">Accounting</option>
                        <option value="Banking and Finance">Banking and Finance</option>
                        <option value="Business Administration">Business Administration</option>
                        <option value="Economics">Economics</option>
                        <option value="International Relations">International Relations</option>
                        <option value="Marketing">Marketing</option>
                    </optgroup>
                </select>
                <br>

                <select name="level" required>
                    <option value="" disabled selected>Select Level</option>
                    <option value="100">100 Level</option>
                    <option value="200">200 Level</option>
                    <option value="300">300 Level</option>
                    <option value="400">400 Level</option>
                    <option value="500">500 Level</option>
                </select>
                <br>

                <input type="file" name="file" accept="application/pdf" required><br>
                <button type="submit">Upload & Process</button>
            </form>
        </body>
    </html>
    """

@app.post("/sync")
def process_sync(department: str = Form(...), level: str = Form(...)):
    """Checks the database and redirects the user to Google Login."""

    # 1. Check if the Course Rep has uploaded this timetable yet in Postgres
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM schedules WHERE department=%s AND level=%s", (department, level))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return HTMLResponse(
            f"<h2>Oops!</h2><p>No timetable found for {department} {level}L. Tell your Course Rep to upload it at the /admin page!</p>")

    # 2. Set up the Web OAuth Flow
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="https://timetable-bot-1-djo2.onrender.com/auth/callback"
    )

    # 3. The "Memory" Trick (State Parameter)
    state_data = json.dumps({"dept": department, "lvl": level})
    safe_state = urllib.parse.quote(state_data)

    # 4. Generate the Google Login URL and send the user there
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=safe_state
    )

    return RedirectResponse(authorization_url, status_code=303)


@app.get("/auth/callback")
def auth_callback(request: Request, code: str, state: str):
    """Google sends the user here after they click 'Allow'."""

    # 1. Decode our "Memory" string to know what they requested
    state_data = json.loads(urllib.parse.unquote(state))
    department = state_data['dept']
    level = state_data['lvl']

    # 2. Exchange the temporary code for actual Calendar access credentials
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/callback"
    )
    # Rebuild the full URL to pass Google's security check
    flow.fetch_token(authorization_response=str(request.url))
    creds = flow.credentials

    # 3. Pull the saved timetable from the Cloud Database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT schedule_json FROM schedules WHERE department=%s AND level=%s", (department, level))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    events = json.loads(row[0])

    # 4. Push to Google Calendar
    service = build("calendar", "v3", credentials=creds)
    today = datetime.date.today()
    next_monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)
    day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4}

    inserted_count = 0
    for event in events:
        day_offset = day_map[event['day']]
        event_date = next_monday + datetime.timedelta(days=day_offset)
        start_time = datetime.datetime.combine(event_date, datetime.time(event['start_hour'], 0))
        end_time = start_time + datetime.timedelta(hours=event['duration'])

        event_body = {
            'summary': event['summary'],
            'location': event['location'],
            'description': event['description'],
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Africa/Lagos'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Africa/Lagos'},
            'recurrence': ['RRULE:FREQ=WEEKLY;COUNT=14'],
            'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 60}]},
        }

        try:
            service.events().insert(calendarId='primary', body=event_body).execute()
            inserted_count += 1
        except Exception as e:
            print(f"Error creating event: {e}")

    # 5. Show the Success Screen!
    return HTMLResponse(f"""
    <html>
        <head>
            <style>body {{ font-family: Arial; text-align: center; margin-top: 100px; }}</style>
        </head>
        <body>
            <h2 style="color: #4CAF50;">Sync Successful! 🎉</h2>
            <p>Added {inserted_count} classes for {department} {level}L to your Google Calendar.</p>
            <p>You can safely close this window.</p>
        </body>
    </html>
    """)


# --- 3. ADMIN UPLOAD PORTAL ---

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    """The hidden page where Course Reps upload the PDFs."""
    return """
    <html>
        <head>
            <title>Course Rep Portal</title>
            <style>
                body { font-family: Arial; margin: 50px; text-align: center; }
                select, input, button { padding: 10px; margin: 10px; font-size: 16px; }
                button { background-color: #008CBA; color: white; border: none; cursor: pointer; }
            </style>
        </head>
        <body>
            <h2>Course Rep Upload Portal</h2>
            <p>Upload the official timetable PDF to the central database.</p>

            <form action="/admin/upload" method="post" enctype="multipart/form-data">
                <select name="department" required>
                    <option value="" disabled selected>Select Department</option>
                    <option value="Mechatronics">Mechatronics Engineering</option>
                    <option value="Aerospace">Aerospace Engineering</option>
                    </select><br>

                <select name="level" required>
                    <option value="" disabled selected>Select Level</option>
                    <option value="100">100 Level</option>
                    <option value="200">200 Level</option>
                    <option value="300">300 Level</option>
                    <option value="400">400 Level</option>
                    <option value="500">500 Level</option>
                </select><br>

                <input type="file" name="file" accept="application/pdf" required><br>
                <button type="submit">Upload & Process</button>
            </form>
        </body>
    </html>
    """


@app.post("/admin/upload")
async def process_upload(department: str = Form(...), level: str = Form(...), file: UploadFile = File(...)):
    """Handles the file, runs your parser, and saves to the database."""

    # 1. Save the uploaded file temporarily
    temp_filename = f"temp_{department}_{level}.pdf"
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())

    try:
        # 2. Run your amazing parsing logic from final_bot.py
        extracted_events = parse_timetable(temp_filename)

        if not extracted_events:
            os.remove(temp_filename)
            return {"error": "Could not find any classes in this PDF. Is it the right format?"}

        # 3. Convert the Python list into a JSON string for the database
        events_json = json.dumps(extracted_events)

        # 4. Save to the Cloud Database (PostgreSQL)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Postgres uses %s instead of ? for parameters
        cursor.execute('''
                       INSERT INTO schedules (department, level, schedule_json)
                       VALUES (%s, %s, %s) ON CONFLICT (department, level) DO
                       UPDATE SET schedule_json = EXCLUDED.schedule_json
                       ''', (department, level, events_json))

        conn.commit()
        cursor.close()
        conn.close()

        # 5. Clean up the temp PDF
        os.remove(temp_filename)

        return {
            "status": "Success!",
            "message": f"Successfully parsed and saved {len(extracted_events)} classes for {department} {level}L."
        }

    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return {"error": f"Something went wrong: {str(e)}"}
