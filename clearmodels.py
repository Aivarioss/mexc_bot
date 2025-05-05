import os

def clear_models():
    model_dir = "models"

    if not os.path.exists(model_dir):
        print("❌ 'models/' mape nav atrasta.")
        return

    count = 0
    empty_count = 0

    for filename in os.listdir(model_dir):
        file_path = os.path.join(model_dir, filename)

        # ✅ Dzēš modeļu failus pēc paplašinājuma
        if filename.endswith(("_model.pkl", "_scaler.pkl", "_features.pkl", "_metrics.json")):
            os.remove(file_path)
            print(f"🗑️ Izdzēsts: {filename}")
            count += 1

        # ✅ Dzēš arī 0-baitu tukšos failus
        elif os.path.isfile(file_path) and os.path.getsize(file_path) == 0:
            os.remove(file_path)
            print(f"🗑️ Tukšs fails izdzēsts: {filename}")
            empty_count += 1

    print(f"\n✅ Notīrīti {count} modeļu faili.")
    print(f"🧹 Tukši faili izdzēsti: {empty_count}")

# Lai skripts strādātu arī standalone
if __name__ == "__main__":
    clear_models()
