import requests, json
token = '5be49902b71187.60586218'

# url = f'https://eodhd.com/api/search/CSSX5E.SW?api_token={token}&fmt=json'
# data = requests.get(url).json()
# print(data)

# url = f'https://eodhd.com/api/eod/CSSX5E.SW?api_token={token}&fmt=json'
# data = requests.get(url).json()
# print(data)

# url = f'https://eodhd.com/api/fundamentals/CSSX5E.SW?api_token={token}&fmt=json'
# data = requests.get(url).json()
# print(data)

r = requests.post(
    "https://api.goetf.ch/analytics/exposure",
    headers={"x-api-key": "39a2R5CpXxjXVIDVlniFRii889BRempM90-f-ItAdy0R0dWew5n_a3a1QFyYWnq7"},
    json={"portfolio": [{"etf_id": "ETF_ID", "weight": 100}]}
)
exposure = r.json()

# url = f'https://eodhd.com/api/exchange-symbol-list/SW?api_token=5be49902b71187.60586218&fmt=json'
# data = requests.get(url).json()
# etfs = [i for i in data if i['Type'] == 'ETF']
# #types = [i for i in data if i['Type'] == 'ETF' and i['Code'] == 'CSSX5E']

# print(etfs)

# import csv
# with open('sw_etf_tickers.csv', 'w', newline='') as csvfile:
#     spamwriter = csv.writer(csvfile, delimiter=' ',
#                             quotechar='|', quoting=csv.QUOTE_MINIMAL)
#     for etf in etfs:
#         spamwriter.writerow([etf['Code']])