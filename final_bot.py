import pdfplumber
import re
import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- CONFIGURATION ---
PDF_PATH = "timetable.pdf"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    """Authenticates and returns the Google Calendar Service"""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def extract_course_details(pdf_path):
    """Reads the bottom of the PDF to find full titles and lecturers"""
    course_metadata = {}

    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()

    print("\n--- Scanning for Lecturers ---")
    lines = text.split('\n')

    for line in lines:
        # Regex to find lines starting with a Number, then MCT/GET code
        # Example: "1 MCT501 Introduction to Robotics 2 2 2 Dr Kafayat..."
        match = re.search(r'(\d+)\s+(MCT\d{3}|GET\d{3})\s+(.*)', line)

        if match:
            code = match.group(2)
            rest_of_line = match.group(3)

            # Heuristic 1: Find the numbers (Credits) to split Title from Lecturer
            # We look for the pattern "2 2 2" or "3 3 3"
            split_match = re.search(r'(.*?)\s+\d\s+\d\s+\d\s+(.*)', rest_of_line)

            if split_match:
                title = split_match.group(1).strip()
                raw_lecturer = split_match.group(2).strip()

                # Cleanup Lecturer Name (remove dashes like "- - Dr...")
                lecturer = raw_lecturer.replace("-", "").strip()

                # Save to dictionary
                course_metadata[code] = {"title": title, "lecturer": lecturer}
                print(f"Detected: {code} | {title} | {lecturer}")

    # Manual Fix for the "Shredded" Course (MCT511)
    if "MCT511" not in course_metadata:
        course_metadata["MCT511"] = {"title": "Process Automation", "lecturer": "Dr Alim A Sabur"}

    return course_metadata


def parse_timetable(pdf_path):
    """Extracts the Grid Schedule"""
    start_times = [8, 9, 10, 11, 12, 13, 14, 15, 16]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    extracted_events = []

    # Get the metadata first
    metadata = extract_course_details(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[0].extract_tables()
        if not tables: return []

        # Grid is the first table
        grid_rows = tables[0][1:6]  # Skip header, take Mon-Fri

        for row_idx, row in enumerate(grid_rows):
            day_name = days[row_idx]
            current_event = None

            for col_idx, cell in enumerate(row):
                if not cell or not cell.strip():
                    if current_event:
                        extracted_events.append(current_event)
                        current_event = None
                    continue

                parts = cell.split('\n')
                course_raw = parts[0].strip()
                venue = parts[1].strip() if len(parts) > 1 else "Unknown Venue"

                # Fix typos (MCT50 3 -> MCT503)
                clean_code = re.sub(r'([A-Z]{3})\s*(\d)\s*(\d)\s*(\d)', r'\1\2\3\4', course_raw)
                clean_code_key = clean_code.replace("(L)", "").strip()  # Remove (L) for lookup

                # Check for merge (continuation)
                if current_event and current_event['code'] == clean_code:
                    current_event['duration'] += 1
                else:
                    if current_event: extracted_events.append(current_event)

                    # Lookup details
                    details = metadata.get(clean_code_key, {"title": "Lecture", "lecturer": "Unknown"})

                    current_event = {
                        "summary": f"{clean_code}: {details['title']}",
                        "description": f"Lecturer: {details['lecturer']}\nVenue: {venue}",
                        "location": venue,
                        "day": day_name,
                        "start_hour": start_times[col_idx],
                        "duration": 1,
                        "code": clean_code
                    }
            if current_event: extracted_events.append(current_event)

    return extracted_events


def create_calendar_events(events):
    service = get_calendar_service()

    # Calculate the date for "Next Monday" to start the schedule
    today = datetime.date.today()
    next_monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)

    print(f"\n--- Syncing to Calendar (Starting Week of {next_monday}) ---")

    day_map = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2,
        "Thursday": 3, "Friday": 4
    }

    for event in events:
        # Calculate exact date and time
        day_offset = day_map[event['day']]
        event_date = next_monday + datetime.timedelta(days=day_offset)

        start_time = datetime.datetime.combine(event_date, datetime.time(event['start_hour'], 0))
        end_time = start_time + datetime.timedelta(hours=event['duration'])

        # Convert to ISO format for Google
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        event_body = {
            'summary': event['summary'],
            'location': event['location'],
            'description': event['description'],
            'start': {'dateTime': start_iso, 'timeZone': 'Africa/Lagos'},
            'end': {'dateTime': end_iso, 'timeZone': 'Africa/Lagos'},
            'recurrence': ['RRULE:FREQ=WEEKLY;COUNT=14'],  # Repeats for 14 weeks (Semester)
            'reminders': {
                'userDefault': False,
                'overrides': [{'method':'popup', 'minutes':60},],
        },
        }

        try:
            service.events().insert(calendarId='primary', body=event_body).execute()
            print(f"Created: {event['summary']} on {event['day']}")
        except Exception as e:
            print(f"Error creating event: {e}")


if __name__ == "__main__":
    # 1. Parse
    all_events = parse_timetable(PDF_PATH)

    # 2. Preview
    print(f"\nFound {len(all_events)} classes. Uploading to Google Calendar...")

    # 3. Upload (Uncomment this line when you are ready!)
    create_calendar_events(all_events)