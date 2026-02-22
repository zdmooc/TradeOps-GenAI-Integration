import httpx

def main():
    r = httpx.get("http://workflow-api:8012/audit?limit=20")
    r.raise_for_status()
    for item in r.json()["items"]:
        print(item)

if __name__ == "__main__":
    main()
