import requests
token = '5be49902b71187.60586218'
url = f'https://eodhd.com/api/eod/SWDA.SW?period=d&api_token={token}&fmt=csv'
data = requests.get(url).content

print(data)