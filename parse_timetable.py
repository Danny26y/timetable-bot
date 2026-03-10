import pdfplumber
import re


def parse_timetable(pdf_path):
    print(f"--- Processing {pdf_path} ---")

    start_times = [8, 9, 10, 11, 12, 13, 14, 15, 16]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    extracted_events = []
    course_metadata = {}

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()

        # --- PART 1: Process the Lecturer Table (Table 2) ---
        if len(tables) >= 2:
            print("Found Lecturer Table! Extracting details...")
            lecturer_table = tables[1]

            for row in lecturer_table[1:]:
                # Filter out empty cells (None or "") to find real data
                clean_row = [cell.strip() for cell in row if cell and cell.strip() != ""]

                # We need at least Code, Title, and Lecturer (approx 3 items)
                if len(clean_row) < 3:
                    continue

                # The Course Code is always first
                code = clean_row[0]

                # The Lecturer is usually the LAST item in the row
                lecturer_name = clean_row[-1]

                # The Title is usually the SECOND item
                title = clean_row[1]

                # Save to dictionary
                course_metadata[code] = {
                    "title": title,
                    "lecturer": lecturer_name
                }
        else:
            print("Warning: Could not find the Lecturer table.")

        # --- PART 2: Process the Grid (Table 1) ---
        if not tables: return []
        grid_table = tables[0]
        data_rows = grid_table[1:6]

        for row_idx, row in enumerate(data_rows):
            day_name = days[row_idx]
            current_event = None

            for col_idx, cell in enumerate(row):
                if not cell or cell.strip() == "":
                    if current_event:
                        extracted_events.append(current_event)
                        current_event = None
                    continue

                # Clean up the text
                parts = cell.split('\n')
                course_raw = parts[0].strip()
                venue = parts[1].strip() if len(parts) > 1 else "Unknown Venue"

                # Fix typos (e.g. MCT50 3 -> MCT503)
                course_code = re.sub(r'([A-Z]{3})\s*([0-9])\s*([0-9])\s*([0-9])', r'\1\2\3\4', course_raw)
                clean_code = course_code.replace("(L)", "").strip()

                # Check for merge
                if current_event and current_event['course_code'] == course_code and current_event['venue'] == venue:
                    current_event['duration'] += 1
                else:
                    if current_event:
                        extracted_events.append(current_event)

                    # LOOKUP
                    # We try to find the code in our metadata keys
                    # Sometimes the code in the grid is "MCT501" but table says "MCT 501"
                    # This simple lookup assumes they match exactly.
                    meta = course_metadata.get(clean_code, {"title": "", "lecturer": "TBA"})

                    current_event = {
                        "day": day_name,
                        "start_hour": start_times[col_idx],
                        "duration": 1,
                        "course_code": course_code,
                        "venue": venue,
                        "course_title": meta['title'],
                        "lecturer": meta['lecturer']
                    }

            if current_event:
                extracted_events.append(current_event)

    return extracted_events


if __name__ == "__main__":
    events = parse_timetable("timetable.pdf")
    print(f"\nFound {len(events)} events with details!")
    for e in events:
        summary = f"{e['course_code']}"
        if e['course_title']: summary += f": {e['course_title']}"
        print(f"{e['day']} @ {e['start_hour']}:00 | {summary}")
        print(f"    Venue: {e['venue']}")
        print(f"    Lecturer: {e['lecturer']}")
        print("-" * 30)