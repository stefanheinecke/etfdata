import requests

def download_amundi_holdings(isin: str, out_file: str):
    session = requests.Session()

    # Step 1: request a download token
    token_resp = session.post(
        "https://www.amundi.com/api/v1/document/download",
        json={
            "isin": isin,
            "documentType": "HOLDINGS",
            "format": "XLSX"
        }
    )
    token_resp.raise_for_status()
    token = token_resp.json()["downloadToken"]

    # Step 2: download the file
    download_url = f"https://www.amundi.com/api/v1/document/download/{token}"
    file_resp = session.get(download_url)
    file_resp.raise_for_status()

    with open(out_file, "wb") as f:
        f.write(file_resp.content)

    return out_file


# Example
download_amundi_holdings("LU2089238625", "amundi_holdings.xlsx")
