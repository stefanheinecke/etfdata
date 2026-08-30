"""Service to enrich holdings data with country, sector, and ISIN information."""
import re
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Mapping of company names/parts to country codes
COUNTRY_PATTERNS = {
    'Germany': ['SIEMENS', 'SAP', 'ALLIANZ', 'DEUTSCHE', 'MERCK', 'BMW', 'BASF', 'DAIMLER', 'INFINEON'],
    'France': ['TOTALENERGIES', 'SANOFI', 'LVMH', 'L\'OREAL', 'AIRBUS', 'SAFRAN', 'SCHNEIDER', 'DANONE', 'EDF'],
    'Spain': ['SANTANDER', 'BILBAO', 'VIZCAYA', 'TELEFONICA', 'IBERDROLA', 'ENDESA', 'REE', 'MAPFRE', 'AMADEUS', 'BBVA'],
    'Italy': ['ENI', 'TENARIS', 'PRYSMIAN', 'EXOR', 'STELLANTIS'],
    'Netherlands': ['ASML', 'SHELL', 'UNILEVER', 'AKZONOBEL', 'NN GROUP'],
    'Belgium': ['SOLVAY', 'INBEV', 'ADYEN', 'ARGENX'],
    'Finland': ['NOKIA', 'KONE', 'SAMPO', 'MAERSK'],
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
        
        # Try to lookup ISIN if not present
        if not holding.get('instrument_isin'):
            holding['instrument_isin'] = HoldingsEnrichmentService._lookup_isin(name)
        
        return holding
    
    @staticmethod
    def _find_country(company_name: str) -> Optional[str]:
        """Find company country based on name patterns."""
        company_upper = company_name.upper()
        
        for country, patterns in COUNTRY_PATTERNS.items():
            for pattern in patterns:
                if pattern.upper() in company_upper:
                    return country
        
        # Try yfinance lookup as fallback
        try:
            import yfinance as yf
            ticker = HoldingsEnrichmentService._extract_ticker(company_name)
            if ticker:
                info = yf.Ticker(ticker).info
                if info and 'country' in info:
                    return info.get('country')
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
    def _lookup_isin(company_name: str) -> Optional[str]:
        """
        Try to lookup ISIN for a company.
        This is difficult without an external API, so for now we return None.
        In production, you might integrate with a financial data provider API.
        """
        # TODO: Integrate with EODHD or another API that can return ISIN
        # For now, return None - the user can fill this in manually
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
