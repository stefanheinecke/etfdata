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

    # Known key-facts row labels, used to tell a genuinely new field apart from
    # a wrapped label continuation (e.g. "Company" continuing "Name of the
    # Management") when stitching multi-line rows back together.
    _KEY_FACTS_LABEL_STARTS = [
        'name of fund', 'share class', 'isin', 'securities no', 'ucits v',
        'launch date', 'currency of fund', 'ter', 'name of the management',
        'accounting year end', 'distribution', 'replication method',
        'portfolio management', 'fund domicile', 'sfdr alignment', 'fund statistics',
        'net asset value', 'last 12 months', 'total fund assets', 'share class assets',
    ]

    @staticmethod
    def _group_words_into_lines(words: List[dict], y_tolerance: float = 3.0) -> List[List[dict]]:
        """Group words into visual lines by their vertical ('top') position."""
        if not words:
            return []
        ordered = sorted(words, key=lambda w: (round(w['top']), w['x0']))
        lines: List[List[dict]] = []
        current: List[dict] = []
        current_top = None
        for w in ordered:
            if current_top is None or abs(w['top'] - current_top) > y_tolerance:
                if current:
                    lines.append(sorted(current, key=lambda w: w['x0']))
                current = [w]
                current_top = w['top']
            else:
                current.append(w)
        if current:
            lines.append(sorted(current, key=lambda w: w['x0']))
        return lines

    @staticmethod
    def _line_segments(line_words: List[dict], gap_threshold: float = 10.0) -> List[List[dict]]:
        """Split a line's words into column segments wherever a large horizontal gap occurs.

        Two-column factsheet pages place unrelated content (e.g. a performance
        chart) at the same vertical position as key-facts rows. Normal word
        spacing is ~2pt; a real column boundary leaves a much larger gap, so
        splitting on gaps > gap_threshold isolates label / value / other-column
        content into separate segments.
        """
        if not line_words:
            return []
        segments: List[List[dict]] = [[line_words[0]]]
        for prev, cur in zip(line_words, line_words[1:]):
            if cur['x0'] - prev['x1'] > gap_threshold:
                segments.append([cur])
            else:
                segments[-1].append(cur)
        return segments

    @staticmethod
    def _find_key_facts_value(pdf, label_re) -> Optional[str]:
        """Read a label's value from the key-facts table using word-level coordinates.

        Splits each visual line into column segments by horizontal gap so that
        a label's own value column is isolated from unrelated content sharing
        the same row (e.g. a performance chart's x-axis labels). Also stitches
        in one continuation line for labels/values that wrap onto two lines
        (e.g. 'Name of the Management' / 'Company').
        """
        for page in pdf.pages[:3]:
            try:
                words = page.extract_words()
            except Exception:
                words = None
            if not words:
                continue
            lines = PDFExtractionService._group_words_into_lines(words)
            line_segments = [PDFExtractionService._line_segments(line) for line in lines]
            for idx, segments in enumerate(line_segments):
                if not segments:
                    continue
                label_text = ' '.join(w['text'] for w in segments[0]).strip()
                if not label_re.match(label_text):
                    continue
                value_parts = []
                if len(segments) > 1:
                    value_parts.append(' '.join(w['text'] for w in segments[1]))
                if idx + 1 < len(line_segments):
                    next_segments = line_segments[idx + 1]
                    if next_segments:
                        next_label = PDFExtractionService._flatten_cell(
                            ' '.join(w['text'] for w in next_segments[0])
                        ).lower()
                        is_new_label = any(
                            next_label == k or next_label.startswith(k)
                            for k in PDFExtractionService._KEY_FACTS_LABEL_STARTS
                        )
                        if not is_new_label and len(next_segments) > 1:
                            value_parts.append(' '.join(w['text'] for w in next_segments[1]))
                value_parts = [v for v in value_parts if v]
                if value_parts:
                    return ' '.join(value_parts).strip()
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
        # Preferred: read the value from the key-facts table row. "Company" is
        # optional here since long labels often wrap onto a second line.
        if pdf is not None:
            company = PDFExtractionService._find_key_facts_value(
                pdf, re.compile(r'Name\s+of\s+(?:the\s+)?Management(?:\s+Company)?', re.IGNORECASE)
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
        import logging
        log = logging.getLogger(__name__)
        
        holdings = []

        # First try to extract from tables
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                log.info(f"[pdf] Page {page_idx}: found {len(tables)} table(s)")
                for table_idx, table in enumerate(tables):
                    # Check if table is actually empty (all cells are None or '')
                    is_empty = all(
                        not row or all(not cell or not str(cell).strip() for cell in row)
                        for row in table
                    )
                    if is_empty:
                        log.info(f"[pdf]   Table {table_idx}: appears empty, skipping")
                        continue
                    
                    extracted = PDFExtractionService._parse_holdings_table(table)
                    log.info(f"[pdf]   Table {table_idx}: parsed {len(extracted) if extracted else 0} holdings")
                    if extracted:  # Only use if we got results
                        holdings.extend(extracted)
            else:
                log.info(f"[pdf] Page {page_idx}: no tables found")

        # If no holdings found in tables, try to parse from text
        if not holdings:
            log.info(f"[pdf] No holdings from tables, falling back to text extraction")
            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    extracted = PDFExtractionService._parse_holdings_from_text(text)
                    if extracted:
                        log.info(f"[pdf] Page {page_idx}: text extraction found {len(extracted)} holdings")
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
        """Parse holdings from text after 'Index 10 largest equity positions' header."""
        import logging
        log = logging.getLogger(__name__)
        
        import re
        holdings = []
        
        # Known sector names from the left "Index Sector exposure" table that we need to skip
        sector_names = [
            'Information Technology', 'Financials', 'Communication Services',
            'Consumer Discretionary', 'Health Care', 'Industrials',
            'Consumer Staples', 'Energy', 'Utilities', 'Real Estate', 'Materials'
        ]
        
        lines = text.split('\n')
        
        # Find the consistent header: "Index 10 largest equity positions"
        holdings_start = None
        for idx, line in enumerate(lines):
            if 'index' in line.lower() and 'largest' in line.lower():
                log.info(f"[pdf] Found holdings header at line {idx}: {line.strip()}")
                holdings_start = idx + 1
                break
        
        if holdings_start is None:
            log.warning("[pdf] Could not find 'Index ... largest' header")
            return holdings
        
        # Parse the table rows after the header
        for idx in range(holdings_start, len(lines)):
            line = lines[idx].strip()
            
            if not line:
                continue
            
            # Stop at end-of-section markers
            if any(keyword in line.lower() for keyword in [
                    'fund statistics', 'key facts', 'costs', 'fund performance',
                    'fund data', 'disclaimer', 'important information', 'risks',
                    'benefits']):
                log.info(f"[pdf] Found section end at line {idx}")
                break
            
            # Skip header rows and sector names (from left table)
            line_upper = line.upper()
            if any(kw in line_upper for kw in ['NAME', 'WEIGHT', 'ISIN', '%', 'INDEX']):
                continue
            
            # Skip known sector names that appear in the left "Sector exposure" table
            if any(sector in line for sector in sector_names):
                log.debug(f"[pdf] Skipping sector line: {line}")
                continue
            
            # Parse: company name followed by percentage
            # Pattern: anything ending with XX.XX percentage
            match = re.search(r'^(.{5,150}?)\s+(\d{1,3}\.\d{2})(?:\s|%|$)', line)
            if match:
                name = match.group(1).strip()
                weight_str = match.group(2)
                
                # Skip if name is a sector or too short
                if any(sector in name for sector in sector_names) or len(name) < 5:
                    continue
                
                try:
                    weight = float(weight_str)
                    if 0 < weight <= 100:
                        holding = {
                            'instrument_name': name,
                            'weight': weight,
                            'instrument_isin': None,
                            'country': None,
                            'sector': None,
                        }
                        holdings.append(holding)
                        log.info(f"[pdf] Parsed: {name} ({weight}%)")
                except ValueError:
                    pass
        
        log.info(f"[pdf] Total parsed: {len(holdings)} holdings")
        return holdings
    

    @staticmethod
    def _parse_holdings_table(table: List[List[str]]) -> List[Dict[str, Any]]:
        """Parse a holdings table extracted from PDF."""
        import logging
        log = logging.getLogger(__name__)
        
        holdings = []

        if not table or len(table) < 2:
            log.warning(f"[pdf] Table too small: {len(table)} rows")
            return holdings

        # Try to identify column headers
        headers = table[0]
        header_lower = [str(h).lower() if h else '' for h in headers]

        # Find relevant column indices with more flexible matching
        name_idx = PDFExtractionService._find_column(header_lower, ['name', 'holding', 'stock', 'isin', 'security', 'position', 'company'])
        weight_idx = PDFExtractionService._find_column(header_lower, ['weight', 'weightage', 'proportion', '%', 'percentage', 'percent'])
        
        print(f"[pdf] Table headers: {headers}")
        print(f"[pdf] Column indices: name={name_idx}, weight={weight_idx}")

        # If we can't identify columns reliably, skip this table (it might be the sector table)
        if name_idx is None or weight_idx is None:
            log.info(f"[pdf] Could not identify name/weight columns, skipping this table")
            return holdings

        # Quick scan: if this table has sector names (Financials, Technology, etc) it's the sector table
        # Check first 10 data rows for sector keywords
        sector_keywords = [
            'information technology', 'financials', 'communication services',
            'consumer discretionary', 'health care', 'industrials',
            'consumer staples', 'energy', 'utilities', 'real estate', 'materials'
        ]
        
        sector_count = 0
        for row in table[1:min(11, len(table))]:
            if name_idx < len(row) and row[name_idx]:
                cell_text = str(row[name_idx]).lower()
                if any(sector in cell_text for sector in sector_keywords):
                    sector_count += 1
        
        if sector_count >= 5:
            log.info(f"[pdf] This table appears to be the sector exposure table (has {sector_count} sector names), skipping")
            return holdings
        
        log.info(f"[pdf] Parsing as holdings table with name_idx={name_idx}, weight_idx={weight_idx}")

        # Parse data rows
        for row in table[1:]:
            if not row:
                continue
            
            # Skip if row is too short
            max_idx = max(filter(lambda x: x is not None, [name_idx, weight_idx]))
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
                    "instrument_isin": None,
                    "raw_identifier": None,
                    "weight": weight,
                    "country": None,
                    "sector": None,
                }
                holdings.append(holding)
                log.info(f"[pdf] Parsed holding: {name} {weight}%")
            except (ValueError, IndexError, AttributeError, TypeError):
                continue

        log.info(f"[pdf] _parse_holdings_table: extracted {len(holdings)} holdings")
        return holdings
    
    @staticmethod
    def _parse_holdings_auto(table: List[List[str]]) -> List[Dict[str, Any]]:
        """Auto-detect and parse holdings when headers are unclear."""
        import logging
        log = logging.getLogger(__name__)
        
        holdings = []
        
        log.info(f"[pdf] Auto-detect: starting, table has {len(table)} rows")
        
        if not table or len(table) < 2:
            log.warning("[pdf] Auto-detect: table too small")
            return holdings
        
        # Dump first 5 rows to see raw structure
        log.info(f"[pdf] Auto-detect: raw table structure (first 5 rows):")
        for i in range(min(5, len(table))):
            log.info(f"[pdf]   row {i}: {repr(table[i][:8] if len(table[i]) > 8 else table[i])}")
        
        # Skip header row(s) that are all empty/None
        data_start = 1
        while data_start < len(table):
            row = table[data_start]
            has_content = row and any(cell and str(cell).strip() for cell in row)
            if has_content:
                log.info(f"[pdf] Auto-detect: first non-empty row at index {data_start}: {row}")
                break
            data_start += 1
        
        if data_start >= len(table):
            log.warning("[pdf] Auto-detect: all rows appear to be headers/empty - table extraction failed, should fallback to text")
            return holdings
        
        # Scan through data rows to find which columns likely contain names vs weights
        name_col = None
        weight_col = None
        
        for row in table[data_start:]:
            if not row or len(row) < 2:
                continue
            
            for col_idx, cell in enumerate(row):
                if not cell:
                    continue
                
                cell_str = str(cell).strip()
                if not cell_str:
                    continue
                
                # Check if this looks like a weight percentage (e.g., "2.86", "45.23")
                try:
                    val = float(cell_str.replace('%', '').replace(',', '.'))
                    if 0 < val <= 100 and weight_col is None:
                        weight_col = col_idx
                        log.info(f"[pdf] Auto-detect: found weight column at index {weight_col} with value {cell_str}")
                        break
                except ValueError:
                    pass
            
            if weight_col is not None:
                break
        
        if weight_col is None:
            log.warning("[pdf] Auto-detect: could not find weight column (no float values 0-100 found)")
            return holdings
        
        # Name is typically in a column before or near the weight column, often the first few columns
        # Try columns before weight first
        name_col = weight_col - 1
        if name_col < 0:
            name_col = 0
        
        log.info(f"[pdf] Auto-detect: using name_col={name_col}, weight_col={weight_col}")
        
        # Now parse holdings using detected columns
        parsed_count = 0
        for row in table[data_start:]:
            if not row or len(row) <= max(name_col, weight_col):
                continue
            
            try:
                name = str(row[name_col]).strip() if row[name_col] else None
                weight_str = str(row[weight_col]).strip() if row[weight_col] else '0'
                
                if not name or name.lower() in ['total', 'name', '']:
                    continue
                
                weight = PDFExtractionService._parse_weight(weight_str)
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
                parsed_count += 1
                if parsed_count <= 5:
                    log.info(f"[pdf] Auto-detect: parsed {name} {weight}%")
            except (ValueError, TypeError, AttributeError, IndexError) as e:
                log.debug(f"[pdf] Auto-detect: error parsing row: {e}")
                continue
        
        log.info(f"[pdf] Auto-detect: finished, parsed {len(holdings)} holdings total")
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
