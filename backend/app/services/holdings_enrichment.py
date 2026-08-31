"""Service to enrich holdings data with country, sector, and ISIN information."""
import os
import re
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

_ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')

# Mapping of company names/parts to country NAMES (for matching)
COUNTRY_PATTERNS = {
    'Germany': ['SIEMENS', 'SAP', 'ALLIANZ', 'DEUTSCHE', 'MERCK', 'BMW', 'BASF', 'DAIMLER', 'INFINEON'],
    'France': ['TOTALENERGIES', 'SANOFI', 'LVMH', 'L\'OREAL', 'AIRBUS', 'SAFRAN', 'SCHNEIDER', 'DANONE', 'EDF'],
    'Spain': ['SANTANDER', 'BILBAO', 'VIZCAYA', 'TELEFONICA', 'IBERDROLA', 'ENDESA', 'REE', 'MAPFRE', 'AMADEUS', 'BBVA'],
    'Italy': ['ENI', 'TENARIS', 'PRYSMIAN', 'EXOR', 'STELLANTIS'],
    'Netherlands': ['ASML', 'SHELL', 'UNILEVER', 'AKZONOBEL', 'NN GROUP'],
    'Belgium': ['SOLVAY', 'INBEV', 'ADYEN', 'ARGENX'],
    'Finland': ['NOKIA', 'KONE', 'SAMPO', 'MAERSK'],
}

# Mapping from country name to ISO 3166-1 alpha-2 code
COUNTRY_TO_ISO2 = {
    'Germany': 'DE',
    'France': 'FR',
    'Spain': 'ES',
    'Italy': 'IT',
    'Netherlands': 'NL',
    'Belgium': 'BE',
    'Finland': 'FI',
    'Luxembourg': 'LU',
    'Switzerland': 'CH',
    'Austria': 'AT',
    'Denmark': 'DK',
    'Sweden': 'SE',
    'Norway': 'NO',
    'Poland': 'PL',
    'Portugal': 'PT',
    'Greece': 'GR',
    'Ireland': 'IE',
    'United Kingdom': 'GB',
    'United States': 'US',
    'Canada': 'CA',
    'Japan': 'JP',
    'China': 'CN',
    'Australia': 'AU',
}

# Mapping of company names/keywords to sectors
SECTOR_PATTERNS = {
    'Financials': ['ALLIANZ', 'SANTANDER', 'BBVA', 'BILBAO', 'VIZCAYA', 'AXA', 'INTESA', 'BANCO', 'STANDARD', 'UBS', 'CREDIT'],
    'Technology': ['SAP', 'SIEMENS', 'ASML', 'INFINEON', 'NOKIA', 'ADYEN'],
    'Industrials': ['SCHNEIDER', 'AIRBUS', 'SAFRAN', 'LEGRAND', 'KONE', 'ATLAS', 'ERICSSON'],
    'Energy': ['TOTALENERGIES', 'SHELL', 'ENI', 'IBERDROLA', 'ENDESA', 'EDF', 'ENEL'],
    'Healthcare': ['SANOFI', 'ROCHE', 'NOVO', 'MERCK', 'ARGENX', 'MORPHIX'],
    'Consumer': ['LVMH', 'L\'OREAL', 'UNILEVER', 'DANONE', 'REMY', 'NESTLÉ'],
    'Materials': ['BASF', 'LINDE', 'SOLVAY', 'RIO TINTO'],
    'Telecommunications': ['DEUTSCHE TELEKOM', 'TELEFONICA', 'BT', 'VODAFONE', 'SWISSCOM', 'ERICSSON'],
}

class HoldingsEnrichmentService:
    """Service to enrich holdings with additional metadata."""
    
    @staticmethod
    def enrich_holding(holding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a holding with country, sector, and attempt to find ISIN.
        
        Args:
            holding: Dict with 'instrument_name' and optionally 'instrument_isin', 'weight', 'country', 'sector'
            
        Returns:
            Enhanced holding dict
        """
        name = holding.get('instrument_name', '').upper()
        
        # Try to determine country
        if not holding.get('country'):
            holding['country'] = HoldingsEnrichmentService._find_country(name)
        
        # Try to determine sector
        if not holding.get('sector'):
            holding['sector'] = HoldingsEnrichmentService._find_sector(name)
        
        # Resolve ISIN: if not present, try raw_identifier (RIC/ticker) via EODHD search
        if not holding.get('instrument_isin'):
            raw_id = holding.pop('raw_identifier', None)
            if raw_id:
                holding['instrument_isin'] = HoldingsEnrichmentService._lookup_isin_from_identifier(raw_id)
            else:
                holding.pop('raw_identifier', None)
        else:
            holding.pop('raw_identifier', None)
        
        return holding
    
    @staticmethod
    def _find_country(company_name: str) -> Optional[str]:
        """Find company country ISO2 code based on name patterns."""
        company_upper = company_name.upper()
        
        # Check pattern-based country matches
        for country_name, patterns in COUNTRY_PATTERNS.items():
            for pattern in patterns:
                if pattern.upper() in company_upper:
                    # Return ISO2 code, not country name
                    return COUNTRY_TO_ISO2.get(country_name, country_name[:2].upper())
        
        # Try yfinance lookup as fallback
        try:
            import yfinance as yf
            ticker = HoldingsEnrichmentService._extract_ticker(company_name)
            if ticker:
                info = yf.Ticker(ticker).info
                if info and 'country' in info:
                    country_from_yf = info.get('country')
                    # Convert country name to ISO2 if needed
                    return COUNTRY_TO_ISO2.get(country_from_yf, country_from_yf[:2].upper() if country_from_yf else None)
        except Exception as e:
            logger.debug(f"yfinance country lookup failed for {company_name}: {e}")
        
        return None
    
    @staticmethod
    def _find_sector(company_name: str) -> Optional[str]:
        """Find company sector based on name patterns."""
        company_upper = company_name.upper()
        
        for sector, patterns in SECTOR_PATTERNS.items():
            for pattern in patterns:
                if pattern.upper() in company_upper:
                    return sector
        
        # Try yfinance lookup as fallback
        try:
            import yfinance as yf
            ticker = HoldingsEnrichmentService._extract_ticker(company_name)
            if ticker:
                info = yf.Ticker(ticker).info
                if info and 'sector' in info:
                    return info.get('sector')
        except Exception as e:
            logger.debug(f"yfinance sector lookup failed for {company_name}: {e}")
        
        return None
    
    @staticmethod
    def _lookup_isin_from_identifier(identifier: str) -> Optional[str]:
        """
        Convert a ticker or RIC code (e.g. 'ALVG.DE', 'NESN.S') to an ISIN via EODHD search.
        Returns the ISIN string or None if not found.
        """
        token = os.getenv("EODHD_TOKEN")
        if not token or not identifier:
            return None
        try:
            import requests
            resp = requests.get(
                f"https://eodhd.com/api/search/{identifier}",
                params={"api_token": token, "fmt": "json", "limit": 3},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            results = resp.json()
            if not results:
                return None
            # Prefer exact ticker match; fall back to first result
            for r in results:
                isin = r.get("ISIN") or r.get("isin")
                if isin and _ISIN_RE.match(isin.upper()):
                    return isin.upper()
        except Exception as e:
            logger.debug(f"EODHD ISIN lookup failed for {identifier}: {e}")
        return None

    @staticmethod
    def _lookup_isin(company_name: str) -> Optional[str]:
        # Legacy stub — use _lookup_isin_from_identifier with a known ticker instead
        return None
    
    @staticmethod
    def _extract_ticker(company_name: str) -> Optional[str]:
        """Try to extract or guess a ticker from company name."""
        # Remove common suffixes and special characters
        name = company_name.upper()
        
        # Remove common words
        for word in ['HLDG', 'AG', 'SA', 'NV', 'N.V', 'SE', 'PLC', 'LTD', 'CORP', 'INC']:
            name = name.replace(word, '').strip()
        
        # Take first 4 characters or known mappings
        ticker_mappings = {
            'ASML': 'ASML',
            'SIEMENS': 'SIE',
            'SAP': 'SAP',
            'ALLIANZ': 'ALV',
            'TOTALENERGIES': 'TTEF',
            'SCHNEIDER': 'SU',
            'SANTANDER': 'SAN',
            'BBVA': 'BBVA',
            'SAFRAN': 'SAF',
        }
        
        # Check known mappings first
        for key, ticker in ticker_mappings.items():
            if key in name:
                return ticker
        
        # Fallback: return first 3-4 letters
        if len(name) >= 3:
            return name[:3]
        
        return None
