import pdfplumber
import tabula
import fitz  # PyMuPDF
import pandas as pd
import sys
import argparse
from pdfminer.layout import LAParams  # Import LAPArams correctly

class PDFExtractor:
    def __init__(self, pdf_path, output_csv, method):
        # Initialize with path to the PDF, output CSV filename, and extraction method
        self.pdf_path = pdf_path
        self.output_csv = output_csv
        self.method = method.lower()

    def extract_with_pdfplumber(self):
        # Configure laparams to try to reduce unnecessary spaces
        params = LAParams(
            line_overlap=0.5,
            char_margin=2.0,
            line_margin=0.5,
            word_margin=0.1
        )

        print("Extracting lines with pdfplumber...")
        all_lines = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # text = page.extract_text(x_tolerance=2, y_tolerance=2, laparams=params)
                text = page.extract_text()
                if text:
                    # Clean up extra spaces in each line
                    # lines = [line.replace(" ", "").strip() for line in text.splitlines()]
                    lines = text.splitlines()
                    all_lines.extend(lines)

        # Save the cleaned lines to a CSV
        df = pd.DataFrame(all_lines, columns=["Text"])
        df.to_csv(self.output_csv, index=False)
        print(f"CSV successfully generated at: {self.output_csv}")

    def extract_with_pdfplumber2(self):
        # Extract line-by-line text using pdfplumber
        print("Extracting lines with pdfplumber...")
        all_lines = []  # List to store all lines of text

        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # Extract the full text and split it into lines
                text = page.extract_text()
                if text:
                    lines = text.splitlines()  # Split the text into lines
                    all_lines.extend(lines)  # Add each line to the list

        # Save the extracted lines to a CSV file
        df = pd.DataFrame(all_lines, columns=["Text"])
        df.to_csv(self.output_csv, index=False)
        print(f"CSV successfully generated at: {self.output_csv}")

    def extract_with_tabula(self):
        # Extract data using tabula-py, which depends on Java for handling tabular PDF data
        print("Extracting with tabula-py...")
        try:
            # Extract all tables from the PDF, processing all pages
            dfs = tabula.read_pdf(self.pdf_path, pages="all", multiple_tables=True)
            df = pd.concat(dfs, ignore_index=True)  # Combine all tables into a single DataFrame
            df.to_csv(self.output_csv, index=False)
            print(f"CSV successfully generated at: {self.output_csv}")
        except Exception as e:
            print(f"An error occurred with tabula-py: {e}")

    def extract_with_pymupdf(self):
        # Extract text data using PyMuPDF, suitable for plain text extraction without structured tables
        print("Extracting with PyMuPDF...")
        with fitz.open(self.pdf_path) as pdf:
            all_text = []  # List to hold all text from each page

            for page in pdf:
                text = page.get_text("text")  # Get text in a line-by-line format
                all_text.append(text)

            # Save the extracted text as a CSV file
            df = pd.DataFrame(all_text, columns=["Text"])
            df.to_csv(self.output_csv, index=False)
            print(f"CSV successfully generated at: {self.output_csv}")

    def run(self):
        # Run the appropriate extraction method based on the user's choice
        if self.method == "pdfplumber":
            self.extract_with_pdfplumber()
        elif self.method == "tabula":
            self.extract_with_tabula()
        elif self.method == "pymupdf":
            self.extract_with_pymupdf()
        else:
            print(f"Method '{self.method}' not recognized. Choose between 'pdfplumber', 'tabula', or 'pymupdf'.")

# Command-line argument setup for running as a script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF to CSV extractor using pdfplumber, tabula-py, or PyMuPDF")
    parser.add_argument("pdf_path", help="Path to the input PDF file")
    parser.add_argument("output_csv", help="Name of the output CSV file")
    parser.add_argument("method", help="Extraction method: 'pdfplumber', 'tabula', or 'pymupdf'")
    
    args = parser.parse_args()

    extractor = PDFExtractor(args.pdf_path, args.output_csv, args.method)
    extractor.run()