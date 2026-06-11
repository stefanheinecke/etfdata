import requests
r = requests.get("https://etfdata-production.up.railway.app/etfs", params={"limit":10},
    headers={"x-api-key":"_jlTM8d5UQbi0gmgpNqTARo8ObzUPXzmMm-s241o49SitxZgrPa7TMsh0KvJk6Jt"})
print(r.json())