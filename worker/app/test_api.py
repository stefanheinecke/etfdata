import requests, json
token = '5be49902b71187.60586218'

url = f'https://eodhd.com/api/fundamentals/CSSX5E.SW?api_token={token}&fmt=json'
data = requests.get(url).json()
etf_data = data.get("ETF_Data") or {}

# Show key fields the import service looks for
print("Name in General:", data["General"].get("Name"))
print("ISIN in ETF_Data:", etf_data.get("ISIN"))
print("ISIN in General:", data["General"].get("ISIN"))
print("TotalExpenseRatio:", etf_data.get("TotalExpenseRatio"))
print("Ongoing_Charge:", etf_data.get("Ongoing_Charge"))
print("OngoingCharge:", etf_data.get("OngoingCharge"))
print("TotalAssets:", etf_data.get("TotalAssets"))
print("Index_Name:", etf_data.get("Index_Name"))
print("Domicile:", etf_data.get("Domicile"))
print("Holdings count:", len(etf_data.get("Holdings") or {}))
# Show first holding
holdings = etf_data.get("Holdings") or {}
if holdings:
    first_key = next(iter(holdings))
    print("First holding key:", first_key)
    print("First holding value:", json.dumps(holdings[first_key], indent=2))