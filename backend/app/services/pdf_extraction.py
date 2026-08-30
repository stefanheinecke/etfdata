import pdfplumber
import re
from typing import Dict, List, Optional, Any
from decimal import Decimal
from io import BytesIO

class PDFExtractionService:
    """Service to extract ETF metadata and holdings from factsheet PDFs."""

    @staticmethod
    def extract_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
        """Extract ETF data from a factsheet PDF."""
        try:
            pdf_file = BytesIO(pdf_bytes)
            
            with pdfplumber.open(pdf_file) as pdf:
                metadata = PDFExtractionService._extract_metadata(pdf)
                holdings = PDFExtractionService._extract_holdings(pdf)
                
                return {
                    "status": "success",
                    "metadata": metadata,
                    "holdings": holdings,
                    "pages": len(pdf.pages)
                }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "metadata": {},
                "holdings": []
            }

    @staticmethod
    def _extract_metadata(pdf) -> Dict[str, Any]:
        """Extract ETF metadata from the PDF."""
        text = ""
        for page in pdf.pages[:3]:  # Check first 3 pages for metadata
            text += page.extract_text() + "\n"

        metadata = {
            "isin": PDFExtractionService._find_isin(text),
            "ticker": PDFExtractionService._find_ticker(text),
            "name": PDFExtractionService._find_etf_name(text),
            "provider": PDFExtractionService._find_provider(text),
            "benchmark": PDFExtractionService._find_benchmark(text),
            "ter": PDFExtractionService._find_ter(text),
            "domicile": PDFExtractionService._find_domicile(text),
            "fund_size": PDFExtractionService._find_fund_size(text),
        }

        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _find_isin(text: str) -> Optional[str]:
        """Find ISIN code in text."""
        match = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b', text)
        return match.group(1) if match else None

    @staticmethod
    def _find_ticker(text: str) -> Optional[str]:
        """Find ticker symbol in text."""
        # Look for patterns like "Ticker: XXXX" or "Symbol: XXXX"
        match = re.search(r'(?:Ticker|Symbol|Listing)[\s:]*([A-Z]{3,6})', text, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _find_etf_name(text: str) -> Optional[str]:
        """Find ETF name in text."""
        lines = text.split('\n')
        # Usually the first non-empty line or within first 5 lines
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 10 and not any(x in line.upper() for x in ['FACTSHEET', 'FUND']):
                # Filter out common non-name lines
                if not re.match(r'^[0-9\-/.]+$', line):
                    return line
        return None

    @staticmethod
    def _find_provider(text: str) -> Optional[str]:
        """Find fund provider/company name."""
        providers = ['iShares', 'Vanguard', 'Amundi', 'Fidelity', 'BlackRock', 
                    'Invesco', 'J.P. Morgan', 'SPDR', 'Xtrackers', 'Lyxor']
        for provider in providers:
            if provider.lower() in text.lower():
                return provider
        return None

    @staticmethod
    def _find_benchmark(text: str) -> Optional[str]:
        """Find benchmark index name."""
        match = re.search(r'(?:Benchmark|Index)[\s:]*([^\n]+?)(?:\n|$)', text, re.IGNORECASE)
        if match:
            benchmark = match.group(1).strip()
            return benchmark if len(benchmark) < 150 else None
        return None

    @staticmethod
    def _find_ter(text: str) -> Optional[float]:
        """Find Total Expense Ratio."""
        # Look for patterns like "TER: 0.25%" or "Expense Ratio: 0.25%"
        match = re.search(r'(?:TER|Total Expense Ratio|Expense Ratio)[\s:]*([0-9.]+)\s*%', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _find_domicile(text: str) -> Optional[str]:
        """Find fund domicile country."""
        countries = {
            'Ireland': ['IE', 'Ireland'],
            'Luxembourg': ['LU', 'Luxembourg'],
            'Switzerland': ['CH', 'Switzerland'],
            'United States': ['US', 'United States'],
            'Germany': ['DE', 'Germany'],
            'France': ['FR', 'France'],
        }
        
        for country, codes in countries.items():
            for code in codes:
                if code in text:
                    return country
        return None

    @staticmethod
    def _find_fund_size(text: str) -> Optional[int]:
        """Find fund asset size."""
        # Look for patterns like "Assets: $1.5B" or "AUM: €500M"
        match = re.search(r'(?:Assets|AUM)[\s:]*\$?€?([0-9.]+)\s*([BMK])', text, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                multiplier = {'B': 1e9, 'M': 1e6, 'K': 1e3}
                mult = multiplier.get(match.group(2).upper(), 1)
                return int(value * mult)
            except (ValueError, KeyError):
                pass
        return None

    @staticmethod
    def _extract_holdings(pdf) -> List[Dict[str, Any]]:
        """Extract holdings table from PDF."""
        holdings = []

        for page in pdf.pages:
            # Try to find tables on the page
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    extracted = PDFExtractionService._parse_holdings_table(table)
                    holdings.extend(extracted)

        # Remove duplicates and sort by weight
        unique_holdings = {h['instrument_name']: h for h in holdings}
        sorted_holdings = sorted(
            unique_holdings.values(),
            key=lambda x: float(x.get('weight', 0)),
            reverse=True
        )

        return sorted_holdings[:100]  # Top 100 holdings

    @staticmethod
    def _parse_holdings_table(table: List[List[str]]) -> List[Dict[str, Any]]:
        """Parse a holdings table extracted from PDF."""
        holdings = []

        if not table or len(table) < 2:
            return holdings

        # Try to identify column headers
        headers = table[0]
        header_lower = [str(h).lower() if h else '' for h in headers]

        # Find relevant column indices
        name_idx = PDFExtractionService._find_column(header_lower, ['name', 'holding', 'stock', 'isin'])
        weight_idx = PDFExtractionService._find_column(header_lower, ['weight', 'weightage', 'proportion', '%'])
        country_idx = PDFExtractionService._find_column(header_lower, ['country', 'country of issue'])
        sector_idx = PDFExtractionService._find_column(header_lower, ['sector', 'industry'])
        isin_idx = PDFExtractionService._find_column(header_lower, ['isin', 'cusip'])

        if name_idx is None or weight_idx is None:
            return []

        # Parse data rows
        for row in table[1:]:
            if not row or len(row) <= max(filter(lambda x: x is not None, 
                                                  [name_idx, weight_idx, country_idx, sector_idx, isin_idx])):
                continue

            try:
                name = str(row[name_idx]).strip() if name_idx < len(row) else None
                weight_str = str(row[weight_idx]).strip() if weight_idx < len(row) else '0'
                
                if not name or name.lower() in ['total', 'name']:
                    continue

                # Clean weight value
                weight = PDFExtractionService._parse_weight(weight_str)
                if weight is None or weight <= 0:
                    continue

                holding = {
                    "instrument_name": name,
                    "instrument_isin": row[isin_idx].strip() if isin_idx and isin_idx < len(row) else None,
                    "weight": weight,
                    "country": row[country_idx].strip() if country_idx and country_idx < len(row) else None,
                    "sector": row[sector_idx].strip() if sector_idx and sector_idx < len(row) else None,
                }

                holdings.append(holding)
            except (ValueError, IndexError, AttributeError):
                continue

        return holdings

    @staticmethod
    def _find_column(headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by keyword matching."""
        for i, header in enumerate(headers):
            for keyword in keywords:
                if keyword in header:
                    return i
        return None

    @staticmethod
    def _parse_weight(weight_str: str) -> Optional[float]:
        """Parse weight value from string."""
        try:
            # Remove common symbols and whitespace
            weight_str = weight_str.replace('%', '').replace(',', '.').strip()
            value = float(weight_str)
            return value if 0 < value <= 100 else None
        except (ValueError, AttributeError):
            return None
