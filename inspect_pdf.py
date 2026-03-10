import pdfplumber


def inspect_pdf(pdf_path):
    print(f"--- Inspecting Rows: {pdf_path} ---")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]  # Just check the first page
        tables = page.extract_tables()

        if tables:
            print(f"Table found with {len(tables[0])} rows.")
            print("-" * 30)
            # Print the first 5 rows to see the pattern
            for i, row in enumerate(tables[0][:6]):
                print(f"ROW {i}: {row}")
                print("-" * 30)
        else:
            print("No tables found.")


if __name__ == "__main__":
    inspect_pdf("timetable.pdf")