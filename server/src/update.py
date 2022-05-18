import json


def update_available(user_info, available):
    with open(user_info) as f:
        info = json.load(f)
        info["available"] = available
    with open(user_info, "w") as f:
        json.dump(info, f)
