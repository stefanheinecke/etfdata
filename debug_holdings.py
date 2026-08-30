import pdfplumber

pdf_path = 'FS_RET_LU0136234068_CH_EN.pdf'

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")
    
    # Look for all tables across all pages
    for page_num, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        if tables:
            print(f"\n{'='*80}")
            print(f"PAGE {page_num + 1} - TABLES FOUND: {len(tables)}")
            print(f"{'='*80}\n")
            
            for table_idx, table in enumerate(tables):
                print(f"\nTable {table_idx + 1} ({len(table)} rows, {len(table[0]) if table else 0} cols):")
                print("Full table:")
                for i, row in enumerate(table):
                    print(f"  Row {i}: {row}")
                    if i >= 15:  # Limit output
                        print(f"  ... ({len(table) - 15} more rows)")
                        break
