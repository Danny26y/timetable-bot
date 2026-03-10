import pdfplumber


def debug_lecturer_table(pdf_path):
    print(f"--- Debugging Table 2 in {pdf_path} ---")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        # We use strict table detection to try and catch faint lines
        tables = page.extract_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"})

        if len(tables) < 2:
            print("Could not find the second table!")
            return

        lecturer_table = tables[1]

        # Print the first 5 rows exactly as the computer sees them
        for i, row in enumerate(lecturer_table[:10]):
            # Replace None with "null" for visibility
            clean_row = ["null" if cell is None else cell.replace("\n", " ") for cell in row]
            print(f"ROW {i}: {clean_row}")


if __name__ == "__main__":
    debug_lecturer_table("timetable.pdf")