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
                # Extract full text for metadata
                full_text = ""
                for page in pdf.pages[:3]:
                    full_text += page.extract_text() + "\n"
                
                metadata = PDFExtractionService._extract_metadata(full_text, pdf)
                holdings = PDFExtractionService._extract_holdings(pdf)
                
                return {
                    "status": "success",
                    "metadata": metadata,
                    "holdings": holdings,
                    "pages": len(pdf.pages)
                }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": str(e),
                "error_detail": traceback.format_exc(),
                "metadata": {},
                "holdings": []
            }

    @staticmethod
    def _extract_metadata(text: str, pdf) -> Dict[str, Any]:
        """Extract ETF metadata from PDF text."""
        metadata = {
            "name": PDFExtractionService._find_etf_name(text),
            "isin": PDFExtractionService._find_isin(text),
            "provider": PDFExtractionService._find_provider(text),
            "ter": PDFExtractionService._find_ter(text),
            "domicile": PDFExtractionService._find_domicile(text),
            "fund_size": PDFExtractionService._find_fund_size(text),
        }
        
        return {k: v for k, v in metadata.items() if v is not None}

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
        """Find ETF name - usually appears in first few lines or after 'Name of fund'."""
        # First try to find after "Name of fund" label
        match = re.search(r'Name\s+of\s+fund\s+([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Look for lines with "UCITS ETF" or similar fund indicators
        lines = text.split('\n')
        for line in lines[:20]:
            line = line.strip()
            if 'UCITS ETF' in line or 'ETF' in line.upper():
                # Remove leading/trailing metadata
                if len(line) > 10 and len(line) < 200:
                    return line
        
        return None

    @staticmethod
    def _find_provider(text: str) -> Optional[str]:
        """Find fund provider/management company name."""
        # Look for "Management Company" or "Manager" patterns
        match = re.search(r'(?:Management\s+Company|Fund\s+Manager|Provider)[\s:]*([^\n]+)', text, re.IGNORECASE)
        if match:
            provider_text = match.group(1).strip()
            # Extract just the company name (before country/city info)
            company_match = re.match(r'([^,()]+)', provider_text)
            if company_match:
                return company_match.group(1).strip()
        
        # Also look for specific known providers
        providers = ['UBS', 'iShares', 'Vanguard', 'Amundi', 'Fidelity', 'BlackRock', 
                    'Invesco', 'SPDR', 'Xtrackers', 'Lyxor', 'Wisdomtree', 'Ishares']
        for provider in providers:
            if provider.lower() in text.lower():
                return provider
        
        return None

    @staticmethod
    def _find_benchmark(text: str) -> Optional[str]:
        """Find benchmark index name."""
        # Look for "Index name" or "Benchmark" patterns
        match = re.search(r'(?:Index\s+name|Benchmark)[\s:]*([^\n]+)', text, re.IGNORECASE)
        if match:
            benchmark = match.group(1).strip()
            # Clean up benchmark name
            benchmark = re.sub(r'\s+(?:Net|Gross|Return|Total|Price|Index).*$', '', benchmark, flags=re.IGNORECASE)
            return benchmark.strip() if benchmark else None
        
        return None

    @staticmethod
    def _find_ter(text: str) -> Optional[float]:
        """Find Total Expense Ratio."""
        # Look for patterns like "TER: 0.25%" or "TER (flat fee) 0.25%"
        match = re.search(r'TER\s*(?:\(flat\s+fee\))?\s*([0-9.]+)\s*%', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        # Also try "Expense Ratio"
        match = re.search(r'(?:Total\s+)?Expense\s+Ratio[\s:]*([0-9.]+)\s*%', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        return None

    @staticmethod
    def _find_domicile(text: str) -> Optional[str]:
        """Find fund domicile country."""
        # Look for "Fund domicile" or "Domicile" pattern
        match = re.search(r'(?:Fund\s+)?Domicile[\s:]*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Also check for country codes and names
        countries = {
            'Luxembourg': ['LU', 'Luxembourg'],
            'Ireland': ['IE', 'Ireland'],
            'Switzerland': ['CH', 'Switzerland'],
            'United States': ['US', 'United States', 'USA'],
            'Germany': ['DE', 'Germany'],
            'France': ['FR', 'France'],
        }
        
        for country, codes in countries.items():
            for code in codes:
                if re.search(rf'\b{code}\b', text):
                    return country
        
        return None

    @staticmethod
    def _find_fund_size(text: str) -> Optional[int]:
        """Find fund asset size."""
        # Look for "Total fund assets" pattern
        match = re.search(r'(?:Total\s+)?fund\s+assets?[\s:]*([0-9.]+)\s*([a-z]*)', text, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                unit = match.group(2).strip().upper()
                
                if not unit or 'M' in unit or 'EUR' in unit or 'USD' in unit:
                    unit = 'M'  # Default to millions
                
                multiplier = {'B': 1e9, 'M': 1e6, 'K': 1e3, 'T': 1e12}
                mult = multiplier.get(unit[0] if unit else 'M', 1e6)
                return int(value * mult)
            except (ValueError, KeyError, IndexError):
                pass
        
        return None

    @staticmethod
    def _extract_holdings(pdf) -> List[Dict[str, Any]]:
        """Extract holdings from PDF - try both tables and text patterns."""
        holdings = []

        # First try to extract from tables
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    extracted = PDFExtractionService._parse_holdings_table(table)
                    if extracted:  # Only use if we got results
                        holdings.extend(extracted)

        # If no holdings found in tables, try to parse from text
        if not holdings:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted = PDFExtractionService._parse_holdings_from_text(text)
                    if extracted:
                        holdings.extend(extracted)

        # Remove duplicates and sort by weight
        unique_holdings = {}
        for h in holdings:
            key = h['instrument_name'].upper()
            if key not in unique_holdings:
                unique_holdings[key] = h
        
        sorted_holdings = sorted(
            unique_holdings.values(),
            key=lambda x: float(x.get('weight', 0)),
            reverse=True
        )

        return sorted_holdings[:100]  # Top 100 holdings

    @staticmethod
    def _parse_holdings_from_text(text: str) -> List[Dict[str, Any]]:
        """Parse holdings from text patterns like 'NAME WEIGHT'."""
        holdings = []
        import re
        
        lines = text.split('\n')
        in_holdings_section = False
        
        for line in lines:
            # Check if we're entering a holdings section
            if 'largest equity positions' in line.lower():
                in_holdings_section = True
                continue
            
            # Check if we're leaving the section
            if in_holdings_section and any(keyword in line.lower() for keyword in ['benefits', 'risks', 'disclaimer']):
                in_holdings_section = False
                continue
            
            if not in_holdings_section:
                continue
            
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Skip header rows
            if 'table_captions' in line.lower() or line.startswith('Index'):
                continue
            
            # Parse holdings from lines with pattern: "NAME1 WEIGHT1 NAME2 WEIGHT2"
            # Weights are always in format XX.XX
            # Use regex to find all "name weight" pairs
            
            # Pattern: (One or more uppercase letters/spaces followed by) (number.number)
            # This matches: "ASML HLDG 8.67 ALLIANZ 3.72" -> [("ASML HLDG", "8.67"), ("ALLIANZ", "3.72")]
            pattern = r'([A-Z][A-Z0-9\s]*?)\s+([0-9]{1,3}\.[0-9]{2})'
            
            matches = re.findall(pattern, line)
            
            for name, weight_str in matches:
                name = name.strip()
                
                # Filter out invalid names
                if not name or len(name) < 2 or len(name) > 100:
                    continue
                
                # Skip rows that are clearly not holdings
                if name.lower() in ['index', 'total', 'other', 'cash'] or name.isdigit():
                    continue
                
                try:
                    weight = float(weight_str)
                    if weight <= 0 or weight > 100:
                        continue
                    
                    holding = {
                        'instrument_name': name,
                        'weight': weight,
                        'instrument_isin': None,
                        'country': None,
                        'sector': None,
                    }
                    holdings.append(holding)
                except ValueError:
                    continue
        
        return holdings

    @staticmethod
    def _parse_holdings_table(table: List[List[str]]) -> List[Dict[str, Any]]:
        """Parse a holdings table extracted from PDF."""
        holdings = []

        if not table or len(table) < 2:
            return holdings

        # Try to identify column headers
        headers = table[0]
        header_lower = [str(h).lower() if h else '' for h in headers]

        # Find relevant column indices with more flexible matching
        name_idx = PDFExtractionService._find_column(header_lower, ['name', 'holding', 'stock', 'isin', 'security', 'position'])
        weight_idx = PDFExtractionService._find_column(header_lower, ['weight', 'weightage', 'proportion', '%', 'percentage', 'percent'])
        country_idx = PDFExtractionService._find_column(header_lower, ['country', 'country of issue', 'domicile'])
        sector_idx = PDFExtractionService._find_column(header_lower, ['sector', 'industry', 'classification'])
        isin_idx = PDFExtractionService._find_column(header_lower, ['isin', 'cusip', 'id', 'code'])

        # If we can't identify columns, try to infer from data
        if name_idx is None or weight_idx is None:
            # Try to detect based on row patterns
            return PDFExtractionService._parse_holdings_auto(table)

        # Parse data rows
        for row in table[1:]:
            if not row:
                continue
            
            # Skip if row is too short
            max_idx = max(filter(lambda x: x is not None, 
                                [name_idx, weight_idx, country_idx, sector_idx, isin_idx]))
            if len(row) <= max_idx:
                continue

            try:
                name = str(row[name_idx]).strip() if name_idx < len(row) and row[name_idx] else None
                weight_str = str(row[weight_idx]).strip() if weight_idx < len(row) and row[weight_idx] else '0'
                
                if not name or name.lower() in ['total', 'name', '']:
                    continue

                # Clean weight value
                weight = PDFExtractionService._parse_weight(weight_str)
                if weight is None or weight <= 0:
                    continue

                holding = {
                    "instrument_name": name,
                    "instrument_isin": row[isin_idx].strip() if isin_idx and isin_idx < len(row) and row[isin_idx] else None,
                    "weight": weight,
                    "country": row[country_idx].strip() if country_idx and country_idx < len(row) and row[country_idx] else None,
                    "sector": row[sector_idx].strip() if sector_idx and sector_idx < len(row) and row[sector_idx] else None,
                }

                holdings.append(holding)
            except (ValueError, IndexError, AttributeError, TypeError):
                continue

        return holdings
    
    @staticmethod
    def _parse_holdings_auto(table: List[List[str]]) -> List[Dict[str, Any]]:
        """Auto-detect and parse holdings when headers are unclear."""
        holdings = []
        
        # For simple tables, assume first column is name, second is weight
        for row in table[1:]:
            if not row or len(row) < 2:
                continue
            
            try:
                # Get first two non-empty elements
                name = None
                weight_str = None
                
                for cell in row:
                    if cell and name is None:
                        name = str(cell).strip()
                    elif cell and weight_str is None:
                        weight_str = str(cell).strip()
                
                if not name or name.lower() in ['total', 'name', '']:
                    continue
                
                weight = PDFExtractionService._parse_weight(weight_str or '0')
                if weight is None or weight <= 0:
                    continue
                
                holding = {
                    "instrument_name": name,
                    "weight": weight,
                    "instrument_isin": None,
                    "country": None,
                    "sector": None,
                }
                holdings.append(holding)
            except (ValueError, TypeError, AttributeError):
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
