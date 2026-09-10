"""Conservative catalog and exposure labels; never infer classification from names."""
import re
import unicodedata


def _key(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


_ASSET_ALIASES = {
    "Equities": ("equity", "stocks", "stock", "shares", "aktien"),
    "Bonds": ("bond", "fixed income", "fixed-income securities", "obligationen", "anleihen", "renten"),
    "Real Estate": ("listed real estate", "listed property", "property", "immobilien", "reits", "reit"),
    "Commodities": ("commodity", "rohstoffe", "precious metals", "edelmetalle", "gold"),
    "Money Market": ("cash", "cash equivalents", "barmittel", "geldmarkt", "money market instruments"),
    "Multi-Asset": ("multi asset", "mixed", "mixed assets", "balanced", "allocation", "mischfonds"),
    "Digital Assets": ("crypto", "cryptocurrency", "cryptocurrencies", "digital asset", "krypto"),
    "Unknown": (),
}
_ASSETS = {_key(alias): category for category, aliases in _ASSET_ALIASES.items()
           for alias in (category, *aliases)}


def normalize_asset_class(value) -> str:
    return _ASSETS.get(_key(value), "Unknown")


def equity_analytics_supported(asset_class) -> bool:
    # Real Estate denotes listed property/REIT ETFs, not direct/private property.
    return normalize_asset_class(asset_class) in {"Equities", "Real Estate"}


def normalize_isin(value):
    """Require ISO 6166 shape and Luhn checksum; missing IDs never share a key."""
    isin = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
        return None
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in isin)
    total = 0
    for i, digit in enumerate(reversed(digits)):
        number = int(digit) * (2 if i % 2 else 1)
        total += number // 10 + number % 10
    return isin if total % 10 == 0 else None


# Only recognized ISO alpha-2 codes and explicit aliases are known exposures.
_COUNTRY_CODES = set("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())
_COUNTRY_NAMES = {
    "US": ("United States", "United States of America", "USA", "U.S.", "Vereinigte Staaten"),
    "GB": ("United Kingdom", "UK", "Great Britain", "Vereinigtes Königreich"),
    "CH": ("Switzerland", "Schweiz"), "DE": ("Germany", "Deutschland"),
    "FR": ("France", "Frankreich"), "JP": ("Japan",), "CN": ("China",),
    "CA": ("Canada", "Kanada"), "AU": ("Australia", "Australien"),
    "NL": ("Netherlands", "Niederlande"), "IE": ("Ireland", "Irland"),
    "SE": ("Sweden", "Schweden"), "DK": ("Denmark", "Dänemark"),
    "FI": ("Finland", "Finnland"), "NO": ("Norway", "Norwegen"),
    "ES": ("Spain", "Spanien"), "IT": ("Italy", "Italien"),
    "BE": ("Belgium", "Belgien"), "AT": ("Austria", "Österreich"),
    "LU": ("Luxembourg", "Luxemburg"), "PT": ("Portugal",),
    "HK": ("Hong Kong",), "TW": ("Taiwan",), "KR": ("South Korea", "Korea (South)", "Republic of Korea", "Korea, Republic of"),
    "IN": ("India", "Indien"), "SG": ("Singapore", "Singapur"),
    "BR": ("Brazil", "Brasilien"), "MX": ("Mexico", "Mexiko"),
    "ZA": ("South Africa", "Südafrika"), "IL": ("Israel",),
    "NZ": ("New Zealand", "Neuseeland"), "PL": ("Poland", "Polen"),
    "SA": ("Saudi Arabia",), "AE": ("United Arab Emirates",),
    "ID": ("Indonesia",), "MY": ("Malaysia",), "TH": ("Thailand",),
    "TR": ("Turkey", "Türkiye"), "GR": ("Greece", "Griechenland"),
    "CL": ("Chile",), "PH": ("Philippines",), "CZ": ("Czech Republic", "Czechia"),
}
_COUNTRIES = {_key(alias): code for code, aliases in _COUNTRY_NAMES.items() for alias in aliases}
_SECTOR_ALIASES = {
    "Information Technology": ("technology", "tech", "it", "informationstechnologie"),
    "Health Care": ("healthcare", "health care", "gesundheitswesen"),
    "Financials": ("financial services", "finance", "financial", "finanzwesen"),
    "Consumer Discretionary": ("consumer cyclical", "zyklische konsumgüter"),
    "Consumer Staples": ("consumer defensive", "nichtzyklische konsumgüter", "basiskonsumgüter"),
    "Communication Services": ("communication", "communications", "telecommunication services", "telecommunications", "kommunikationsdienste"),
    "Industrials": ("industrial", "industrie"),
    "Materials": ("basic materials", "grundstoffe"),
    "Energy": ("energie",), "Utilities": ("versorger",),
    "Real Estate": ("realestate", "immobilien"),
}
_SECTORS = {_key(alias): sector for sector, aliases in _SECTOR_ALIASES.items()
            for alias in (sector, *aliases)}


def normalize_bucket(value, allocation_type):
    if allocation_type == "country":
        code = str(value or "").strip().upper()
        return code if code in _COUNTRY_CODES else _COUNTRIES.get(_key(value))
    if allocation_type == "sector":
        return _SECTORS.get(_key(value))
    if allocation_type == "currency":
        code = str(value or "").strip().upper()
        return code if code in {"USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD", "NZD", "CNY", "CNH", "HKD", "SGD", "SEK", "NOK", "DKK", "KRW", "TWD", "INR", "BRL", "ZAR", "MXN", "PLN", "ILS", "AED", "ARS", "BDT", "BHD", "CLP", "COP", "CZK", "EGP", "HUF", "IDR", "ISK", "JOD", "KES", "KWD", "LKR", "MAD", "MYR", "NGN", "OMR", "PEN", "PHP", "PKR", "QAR", "RON", "RUB", "SAR", "THB", "TRY", "UAH", "VND"} else None
    return None