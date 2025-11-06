# Test Fixtures

This directory contains test fixtures for the PDF extraction test suite.

## Test PDFs

To generate test PDF files, run:

```bash
python tests/fixtures/create_test_pdfs.py
```

This will create the following test PDFs:

- `sample_oab.pdf` - Sample OAB professional card with typical fields
- `simple_document.pdf` - Simple document with basic fields
- `multifield_document.pdf` - Document with many fields for comprehensive testing
- `empty_document.pdf` - Empty PDF with no text content

## Requirements

The PDF generation script requires reportlab:

```bash
pip install reportlab
```

## Usage in Tests

These PDFs can be used in integration tests that require real PDF files. For most unit tests, mocked pdfplumber objects are preferred for faster execution.

Example:

```python
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
sample_pdf = FIXTURES_DIR / "sample_oab.pdf"
```
