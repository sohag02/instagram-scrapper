import requests

def verify_proxy(proxy:str):
    proxies = {
        "http": proxy,
        "https": proxy,
    }
    try:
        r = requests.get(
            "https://api.ipify.org?format=json",
            proxies=proxies,
            timeout=10
        )
        print("Proxy works. IP:", r.json()["ip"])
        return True
    except Exception as e:
        print("Proxy failed:", e)
        return False

if __name__ == "__main__":
    proxy = input("Enter proxy: ")
    verify_proxy(proxy)
