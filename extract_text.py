import pdfplumber
import re

pdf_path = 'FS_RET_LU0136234068_CH_EN.pdf'

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text()
        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1} - TEXT CONTENT")
        print(f"{'='*80}\n")
        print(text)
        print("\n\n")
