"""Service to enrich holdings data with country, sector, and ISIN information."""
import re
import threading
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

_ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')
# Serialise all yfinance .info calls to avoid the cookie/session threading bug
_yf_lock = threading.Lock()

# Mapping of company names/parts to country NAMES (for matching)
COUNTRY_PATTERNS = {
    'Germany': ['SIEMENS', 'SAP', 'ALLIANZ', 'DEUTSCHE', 'MERCK', 'BMW', 'BASF', 'DAIMLER', 'INFINEON'],
    'France': ['TOTALENERGIES', 'SANOFI', 'LVMH', 'L\'OREAL', 'AIRBUS', 'SAFRAN', 'SCHNEIDER', 'DANONE', 'EDF'],
    'Spain': ['SANTANDER', 'BILBAO', 'VIZCAYA', 'TELEFONICA', 'IBERDROLA', 'ENDESA', 'REE', 'MAPFRE', 'AMADEUS', 'BBVA'],
    'Italy': ['ENI', 'TENARIS', 'PRYSMIAN', 'EXOR', 'STELLANTIS'],
    'Netherlands': ['ASML', 'SHELL', 'UNILEVER', 'AKZONOBEL', 'NN GROUP'],
    'Belgium': ['SOLVAY', 'INBEV', 'ADYEN', 'ARGENX'],
    'Finland': ['NOKIA', 'KONE', 'SAMPO', 'MAERSK'],
    'United States': ['APPLE', 'MICROSOFT', 'NVIDIA', 'AMAZON', 'ALPHABET', 'TESLA', 'META', 'BROADCOM', 'JPMORGAN', 'BERKSHIRE', 'GOLDMAN', 'MORGAN STANLEY', 'BANK OF AMERICA', 'WELLS FARGO', 'COCA COLA', 'PEPSI', 'INTEL', 'AMD', 'QUALCOMM', 'CISCO', 'IBM', 'ORACLE', 'SALESFORCE'],
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
    'Financials': ['ALLIANZ', 'SANTANDER', 'BBVA', 'BILBAO', 'VIZCAYA', 'AXA', 'INTESA', 'BANCO', 'STANDARD', 'UBS', 'CREDIT', 'JPMORGAN', 'GOLDMAN', 'MORGAN STANLEY', 'BANK OF AMERICA', 'WELLS FARGO', 'BERKSHIRE'],
    'Technology': ['SAP', 'SIEMENS', 'ASML', 'INFINEON', 'NOKIA', 'ADYEN', 'APPLE', 'MICROSOFT', 'NVIDIA', 'ALPHABET', 'INTEL', 'AMD', 'QUALCOMM', 'CISCO', 'IBM', 'ORACLE', 'SALESFORCE', 'BROADCOM'],
    'Industrials': ['SCHNEIDER', 'AIRBUS', 'SAFRAN', 'LEGRAND', 'KONE', 'ATLAS', 'ERICSSON'],
    'Energy': ['TOTALENERGIES', 'SHELL', 'ENI', 'IBERDROLA', 'ENDESA', 'EDF', 'ENEL'],
    'Healthcare': ['SANOFI', 'ROCHE', 'NOVO', 'MERCK', 'ARGENX', 'MORPHIX'],
    'Consumer': ['LVMH', 'L\'OREAL', 'UNILEVER', 'DANONE', 'REMY', 'NESTLÉ', 'COCA COLA', 'PEPSI', 'AMAZON', 'META', 'TESLA'],
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
        
        # Resolve ISIN: try raw_identifier (RIC/ticker) first
        if not holding.get('instrument_isin'):
            raw_id = holding.pop('raw_identifier', None)
            if raw_id:
                print(f"[holdings] Looking up ISIN for ticker: {raw_id}")
                holding['instrument_isin'] = HoldingsEnrichmentService._lookup_isin_from_ticker(raw_id)
                print(f"[holdings] {raw_id} -> {holding['instrument_isin']}")
            # Name-only holdings: no reliable free lookup — leave ISIN null
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
        
        return None
    
    @staticmethod
    def _find_sector(company_name: str) -> Optional[str]:
        """Find company sector based on name patterns."""
        company_upper = company_name.upper()
        
        for sector, patterns in SECTOR_PATTERNS.items():
            for pattern in patterns:
                if pattern.upper() in company_upper:
                    return sector
        
        return None
    
    @staticmethod
    def _lookup_isin_from_ticker(ticker: str) -> Optional[str]:
        """
        Fetch ISIN for a ticker/RIC (e.g. 'ALVG.DE') via yfinance .info.
        Safe because a proper ticker string does NOT trigger yfinance's buggy
        internal ISIN detection (only ISIN-format strings do).
        """
        if not ticker:
            return None
        try:
            import yfinance as yf
            with _yf_lock:
                info = yf.Ticker(ticker).info
            isin = info.get("isin") or info.get("ISIN")
            if isin and _ISIN_RE.match(str(isin).upper()):
                return str(isin).upper()
        except Exception as e:
            logger.debug(f"yfinance ISIN lookup failed for {ticker}: {e}")
        return None

    @staticmethod
    def _lookup_isin_from_identifier(identifier: str) -> Optional[str]:
        # Legacy alias
        return HoldingsEnrichmentService._lookup_isin_from_ticker(identifier)

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
