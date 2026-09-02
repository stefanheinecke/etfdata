import pdfplumber
import re
from typing import Dict, List, Optional, Any
from decimal import Decimal
from io import BytesIO

_ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')

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
        dividend_policy = PDFExtractionService._find_dividend_policy(text)
        metadata = {
            "name": PDFExtractionService._find_etf_name(text, pdf, dividend_policy),
            "isin": PDFExtractionService._find_isin(text),
            "provider": PDFExtractionService._find_provider(text, pdf),
            "ter": PDFExtractionService._find_ter(text),
            "domicile": PDFExtractionService._find_domicile(text),
            "fund_size": PDFExtractionService._find_fund_size(text),
            "replication_method": PDFExtractionService._find_replication_method(text),
            "dividend_policy": dividend_policy,
        }
        
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _flatten_cell(s: Optional[str]) -> str:
        return re.sub(r'\s+', ' ', s or '').strip()

    # Known key-facts row labels, used to tell a wrapped label continuation
    # (e.g. "Company" continuing "Name of the Management") apart from the
    # start of a genuinely new field.
    _KEY_FACTS_LABEL_STARTS = [
        'name of fund', 'share class', 'isin', 'securities no', 'ucits v',
        'launch date', 'currency of fund', 'ter', 'name of the management',
        'accounting year end', 'distribution', 'replication method',
        'portfolio management', 'fund domicile', 'sfdr alignment', 'fund statistics',
    ]

    @staticmethod
    def _find_key_facts_column(lines: List[str]) -> Optional[int]:
        """Determine the value column's character offset using a reliable anchor row.

        The key-facts section is a fixed two-column table rendered with
        layout-preserved spacing, so every row's value starts at the same
        character column. 'ISIN' is a short, virtually universal, single-line
        label that makes a reliable anchor.
        """
        for anchor in ('ISIN', 'UCITS V', 'SFDR Alignment', 'Fund domicile'):
            pat = re.compile(rf'^\s{{0,3}}{re.escape(anchor)}\s{{2,}}', re.IGNORECASE)
            for line in lines:
                m = pat.match(line)
                if m:
                    return m.end()
        return None

    @staticmethod
    def _find_key_facts_value(pdf, label_re) -> Optional[str]:
        """Read a label's value from the key-facts table using its fixed value column.

        Restricting the label search to the label column (left of the value
        column boundary) avoids false matches such as 'share class' inside
        'Currency of fund / share class', since long labels wrap onto a second
        line rather than spilling into the value column. Also stitches in one
        continuation line for labels/values that wrap (e.g. 'Name of the
        Management' / 'Company').
        """
        for page in pdf.pages[:3]:
            try:
                text = page.extract_text(layout=True)
            except Exception:
                text = None
            if not text:
                continue
            lines = text.split('\n')
            col = PDFExtractionService._find_key_facts_column(lines)
            if col is None:
                continue
            for idx, line in enumerate(lines):
                label_part = line[:col] if len(line) > col else line
                if not label_re.search(label_part):
                    continue
                value_parts = []
                v = line[col:].strip() if len(line) > col else ''
                if v:
                    value_parts.append(v)
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    next_label = PDFExtractionService._flatten_cell(
                        next_line[:col] if len(next_line) > col else next_line
                    ).lower()
                    is_new_label = any(
                        next_label.startswith(k) for k in PDFExtractionService._KEY_FACTS_LABEL_STARTS
                    ) if next_label else False
                    if not is_new_label:
                        nv = next_line[col:].strip() if len(next_line) > col else ''
                        if nv:
                            value_parts.append(nv)
                if value_parts:
                    return ' '.join(value_parts)
        return None

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
    def _find_etf_name(text: str, pdf=None, dividend_policy: Optional[str] = None) -> Optional[str]:
        """Find ETF share class name - e.g. 'UBS Core MSCI EMU UCITS ETF EUR dis'.

        Prefers the 'Share class' row, which already includes the currency and
        distribution suffix, so different variants of the same fund are
        distinguishable.
        """
        # Preferred: the "Share class" row already has the full share-class name
        if pdf is not None:
            share_class = PDFExtractionService._find_key_facts_value(pdf, re.compile(r'\bShare\s+class\b', re.IGNORECASE))
            if share_class:
                return share_class

        base_name = None
        # Fallback: "Name of fund" row (base fund name, no share-class suffix)
        if pdf is not None:
            base_name = PDFExtractionService._find_key_facts_value(pdf, re.compile(r'Name\s+of\s+fund\b', re.IGNORECASE))
        if not base_name:
            match = re.search(r'Name\s+of\s+(?:the\s+)?fund\s+([^\n]+)', text, re.IGNORECASE)
            if match:
                base_name = match.group(1).strip()
        if not base_name:
            # Look for lines with "UCITS ETF" or similar fund indicators
            lines = text.split('\n')
            for line in lines[:20]:
                line = line.strip()
                if 'UCITS ETF' in line or 'ETF' in line.upper():
                    # Remove leading/trailing metadata
                    if len(line) > 10 and len(line) < 200:
                        base_name = line
                        break

        if not base_name:
            return None

        # Append share class suffix (currency + dis/acc) if not already present
        suffix_parts = []
        currency = PDFExtractionService._find_share_class_currency(text)
        if currency and currency.upper() not in base_name.upper():
            suffix_parts.append(currency.upper())
        if dividend_policy:
            short = 'acc' if dividend_policy == 'Accumulating' else 'dis'
            if not re.search(r'\b(acc|dis|dist|inc)\b', base_name, re.IGNORECASE):
                suffix_parts.append(short)

        if suffix_parts:
            return f"{base_name} {' '.join(suffix_parts)}"
        return base_name

    @staticmethod
    def _find_share_class_currency(text: str) -> Optional[str]:
        """Find the share class trading currency (e.g. 'Share class currency: EUR')."""
        match = re.search(
            r'(?:Share\s+class\s+currency|Trading\s+currency|Currency\s+of\s+share\s+class|W\u00e4hrung\s+der\s+Anteilsklasse)'
            r'[:\s]+([A-Z]{3})\b',
            text, re.IGNORECASE
        )
        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def _find_provider(text: str, pdf=None) -> Optional[str]:
        """Find fund provider - the full "Name of the Management Company" value."""
        # Preferred: read the value from the key-facts table row
        if pdf is not None:
            company = PDFExtractionService._find_key_facts_value(
                pdf, re.compile(r'Name\s+of\s+(?:the\s+)?Management\s+Company', re.IGNORECASE)
            )
            if company:
                return company

        # Fallback: explicit "Name of the Management Company" field on flattened text
        match = re.search(r'Name\s+of\s+(?:the\s+)?Management\s+Company[\s:]*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback: "Management Company" / "Fund Manager" / "Provider" patterns
        match = re.search(r'(?:Management\s+Company|Fund\s+Manager|Provider)[\s:]*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
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
        # Match TER followed by any text (including German parentheticals) then a number%
        # Handles: "TER: 0.25%", "TER (flat fee) 0.25%", "TER (Pauschale 0.09%" (German)
        match = re.search(r'TER[^%]{0,80}?([0-9]+[.,][0-9]+)\s*%', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
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
        """Find fund asset size (handles EN 'Total fund assets' and DE 'Gesamtfondsvermögen')."""
        match = re.search(
            r'(?:Total\s+fund\s+assets?|Gesamtfondsverm\u00f6gen)[^\n]*?'
            r'(\d{1,3}(?:\s\d{3})*[.,]\d+|\d{1,3}(?:,\d{3})*\.\d+|\d+[.,]\d+|\d+)',
            text, re.IGNORECASE
        )
        if match:
            try:
                raw = match.group(1).strip()
                raw = re.sub(r'(?<=\d)\s(?=\d{3}\b)', '', raw)   # "7 473.77" → "7473.77"
                raw = re.sub(r',(?=\d{3}[.,])', '', raw)           # "3,966.80" → "3966.80"
                raw = raw.replace(',', '.')
                value = float(raw)
                # Determine unit from the parenthetical on the same line
                line = re.search(r'(?:Total\s+fund\s+assets?|Gesamtfondsverm\u00f6gen)([^\n]*)', text, re.IGNORECASE)
                unit_str = line.group(1) if line else ''
                if re.search(r'\b(bn|billion)\b', unit_str, re.IGNORECASE):
                    return int(value * 1_000_000_000)
                return int(value * 1_000_000)  # default: millions (mn / mio / m)
            except (ValueError, AttributeError):
                pass
        return None

    @staticmethod
    def _find_replication_method(text: str) -> Optional[str]:
        """Find replication method (EN 'Replication method/methodology' and DE 'Replikationsmethode')."""
        match = re.search(
            r'(?:Replication\s+method(?:ology)?|Replikationsmethode)[:\s]+([^\n]+)',
            text, re.IGNORECASE
        )
        if match:
            val = match.group(1).strip().lower()
            if 'physical' in val or 'physisch' in val or 'voll' in val or 'full' in val:
                return 'Physical (Full replication)'
            if 'sampling' in val or 'stichprob' in val or 'optimis' in val or 'representative' in val:
                return 'Physical (Sampling)'
            if 'synthetic' in val or 'synthetisch' in val or 'swap' in val:
                return 'Synthetic'
            return match.group(1).strip()[:80]
        return None

    @staticmethod
    def _find_dividend_policy(text: str) -> Optional[str]:
        """Find dividend policy from explicit field or share class name."""
        # Explicit field: EN 'Distribution' / DE 'Aussch\u00fcttung'
        match = re.search(
            r'(?:Distribution(?:\s+policy)?|Aussch\u00fcttung)[:\s]+([^\n]+)',
            text, re.IGNORECASE
        )
        if match:
            val = match.group(1).strip().lower()
            if any(k in val for k in ('accum', 'thesauri', 'reinvest')):
                return 'Accumulating'
            if any(k in val for k in ('distrib', 'income', 'aussch')):
                return 'Distributing'
        # Fallback: last token of share class name
        sc_match = re.search(r'(?:Share\s+class|Anteilsklasse)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if sc_match:
            last = sc_match.group(1).strip().split()[-1].lower()
            if last in ('acc', 'accumulating'):
                return 'Accumulating'
            if last in ('dis', 'dist', 'distributing', 'inc', 'income'):
                return 'Distributing'
        # Last resort: bare keyword in text
        if re.search(r'\bacc\b', text):
            return 'Accumulating'
        if re.search(r'\b(?:dis|dist)\b', text, re.IGNORECASE):
            return 'Distributing'
        return None

    @staticmethod
    def _extract_holdings(pdf) -> List[Dict[str, Any]]:
        """Extract holdings from PDF - try both tables and text patterns."""
        from app.services.holdings_enrichment import HoldingsEnrichmentService
        
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

        # Enrich holdings with country, sector, and ISIN
        enriched_holdings = []
        for holding in sorted_holdings[:100]:  # Top 100 holdings
            enriched_holding = HoldingsEnrichmentService.enrich_holding(holding)
            enriched_holdings.append(enriched_holding)

        return enriched_holdings

    @staticmethod
    def _parse_holdings_from_text(text: str) -> List[Dict[str, Any]]:
        """Parse holdings from text patterns like 'NAME WEIGHT'."""
        holdings = []
        import re
        
        lines = text.split('\n')
        in_holdings_section = False
        
        for line in lines:
            # Check if we're entering a holdings section (English or German)
            line_lower = line.lower()
            if ('largest equity positions' in line_lower
                    or 'gr\u00f6sste' in line_lower
                    or 'aktienpositionen' in line_lower
                    or 'top holdings' in line_lower
                    or 'top 10' in line_lower):
                in_holdings_section = True
                continue
            
            # Check if we're leaving the section (English or German)
            if in_holdings_section and any(keyword in line_lower for keyword in [
                    'benefits', 'risks', 'disclaimer', 'vorteile', 'risiken', 'disclaimer']):
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
            
            # Pattern: matches both ALL-CAPS (e.g. ASML HLDG) and Title Case (e.g. Taiwan Semiconductor)
            pattern = r'([A-Za-z][A-Za-z0-9\s]*?)\s+([0-9]{1,3}\.[0-9]{2})'
            
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
        isin_idx = PDFExtractionService._find_column(header_lower, ['isin', 'cusip', 'sedol', 'valoren', 'ticker', 'ric', 'reuters', 'bloomberg', 'id', 'code', 'symbol'])
        print(f"[pdf] Table headers: {headers}")
        print(f"[pdf] Column indices: name={name_idx}, weight={weight_idx}, isin/id={isin_idx}, country={country_idx}, sector={sector_idx}")

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

                raw_id = row[isin_idx].strip() if isin_idx and isin_idx < len(row) and row[isin_idx] else None
                # Only keep value as ISIN if it matches the format; otherwise treat it as a ticker/RIC for enrichment lookup
                if raw_id and _ISIN_RE.match(raw_id.upper()):
                    instrument_isin = raw_id.upper()
                    raw_identifier = None
                else:
                    instrument_isin = None
                    raw_identifier = raw_id  # e.g. Reuters RIC like "NESN.S"

                holding = {
                    "instrument_name": name,
                    "instrument_isin": instrument_isin,
                    "raw_identifier": raw_identifier,
                    "weight": weight,
                    "country": row[country_idx].strip() if country_idx and country_idx < len(row) and row[country_idx] else None,
                    "sector": row[sector_idx].strip() if sector_idx and sector_idx < len(row) and row[sector_idx] else None,
                }
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
