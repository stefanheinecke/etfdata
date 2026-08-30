import sys
sys.path.insert(0, 'backend')

from app.services.pdf_extraction import PDFExtractionService

pdf_path = 'FS_RET_LU0136234068_CH_EN.pdf'

with open(pdf_path, 'rb') as f:
    pdf_bytes = f.read()

result = PDFExtractionService.extract_from_pdf(pdf_bytes)

print("Status:", result['status'])
print("\nMetadata:")
for key, value in result['metadata'].items():
    print(f"  {key}: {value}")

print(f"\nHoldings found: {len(result['holdings'])}")
print("\nFirst 15 holdings:")
for holding in result['holdings'][:15]:
    print(f"  {holding['instrument_name']}: {holding['weight']}%")
