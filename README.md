# Introduction

...

Modules for data extraction:

- [pdfplumber](https://pypi.org/project/pdfplumber/)
- [tabula-py](https://tabula-py.readthedocs.io/en/latest/)
- [pymupdf](https://pymupdf.readthedocs.io/en/latest/)

Python project tools:

- Cookiecutter
- Poetry
- PyScaffold

# Roadmap

- [ ] Projece structure
  - [x] Upload to Github
  - [ ] Create skeleton using one of the proposed tools
- [ ] Data extraction
  - [ ] Create script to automatically convert from PDF to CSV using each method (pdfplumger, tabula-py and PyMuPDF)
  - [ ] Try variations (laparams for pdfplumber, coordinates for PyMyPDF, maybe in tabula-py too) and adjust for each document type
  - [ ] Split into modules for HSBC Visa, HSBC MasterCard, HSBC CA and BBVA Visa
  - [ ] Upload one sample per module (without names and changed amounts) to Github for unit tests and development
  - [ ] Add automatic detection for each module, and an error if a more than one apply for a PDF
  - [ ] For each extraction module, add warnings if a line looks like an amount but can't be extracted
- [ ] Statement processing
  - [ ] Allow processing multiple files at once, generating summaries (carrying over installments) in a CSV or Excel
  - [ ] Search entry names using ChatGPT to classify, or ask it to generate a pattern for local classification
  - [ ] Support extension cards
  - [ ] Support amounts in ARS and USD
  - [ ] Support previous statement amount, taxes, etc
- [ ] Next steps
  - [ ] Add a basic web UI and deploy, allowing multiple uploads