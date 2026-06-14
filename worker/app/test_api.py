import requests, json
token = '5be49902b71187.60586218'

url = f'https://eodhd.com/api/search/CSSX5E.SW?api_token={token}&fmt=json'
data = requests.get(url).json()
print(data)

# url = f'https://eodhd.com/api/eod/CSSX5E.SW?api_token={token}&fmt=json'
# data = requests.get(url).json()
# print(data)

url = f'https://eodhd.com/api/fundamentals/CSSX5E.SW?api_token={token}&fmt=json'
data = requests.get(url).json()
print(data)