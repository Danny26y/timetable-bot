import pdfplumber


def debug_text(pdf_path):
    print(f"--- Extracting Raw Text from {pdf_path} ---")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()

        print("\n--- RAW TEXT DUMP ---")
        # Print line by line so we can see the structure
        for i, line in enumerate(text.split('\n')):
            print(f"Line {i}: {line}")


if __name__ == "__main__":
    debug_text("timetable.pdf")