import os, requests, yaml
from dotenv import load_dotenv
load_dotenv()
CFG = yaml.safe_load(open("config.yaml", encoding="utf-8"))
URL = CFG["robot"]["url"]; TO = CFG["robot"]["timeout"]
HDR = {"x-token": os.environ.get("CHINNU_TOKEN", "")}

def health():
    return requests.get(f"{URL}/health", timeout=5).json()

def action(name: str):
    r = requests.post(f"{URL}/action/{name}", headers=HDR, timeout=TO)
    return r.json() if r.ok else {"ok": False, "error": r.text}

def stop():
    return requests.post(f"{URL}/stop", headers=HDR, timeout=5).json()

if __name__ == "__main__":
    print(health()); print(action("wag_tail"))
