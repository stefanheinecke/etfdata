import pdfplumber
import json

pdf_path = 'FS_RET_LU0136234068_CH_EN.pdf'

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")
    
    # Extract text from first 3 pages
    for page_num in range(min(3, len(pdf.pages))):
        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1}")
        print(f"{'='*80}\n")
        
        page = pdf.pages[page_num]
        text = page.extract_text()
        print(text)
        
        # Also show tables on this page
        tables = page.extract_tables()
        if tables:
            print(f"\n--- TABLES ON PAGE {page_num + 1} ---")
            for i, table in enumerate(tables):
                print(f"\nTable {i + 1}:")
                for row in table[:10]:  # First 10 rows
                    print(row)
