import os

SOURCE_DIR = "bitget_bot"

REPLACEMENTS = {
    "MexcClient": "BitgetClient",
    "modules.mexc_fetcher": "modules.bitget_client",
    "mexc.": "bitget.",  # ja tiek izmantots tā
    "mexc_": "bitget_",  # ja mainīgie
    "MEXC": "BITGET"     # env mainīgajiem
}

def convert_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    updated = code
    for old, new in REPLACEMENTS.items():
        updated = updated.replace(old, new)

    if updated != code:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"[✓] Konvertēts: {filepath}")

def walk_files():
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            if file.endswith(".py"):
                convert_file(os.path.join(root, file))

if __name__ == "__main__":
    walk_files()
