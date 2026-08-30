import pdfplumber

pdf_path = 'FS_RET_LU0136234068_CH_EN.pdf'

with pdfplumber.open(pdf_path) as pdf:
    for page_num in range(min(3, len(pdf.pages))):
        page = pdf.pages[page_num]
        text = page.extract_text()
        
        if 'largest equity positions' in text.lower():
            print(f"Found holdings section on page {page_num + 1}\n")
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                if 'largest equity positions' in line.lower():
                    # Print surrounding lines
                    for j in range(max(0, i-2), min(len(lines), i+20)):
                        print(f"Line {j}: [{lines[j]}]")
                    break
