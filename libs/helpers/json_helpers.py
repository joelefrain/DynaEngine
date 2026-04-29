import json

def export_dict_to_json(output_path, data_to_json):
    with open(output_path, "w", encoding="utf-8") as f:
       json.dump(data_to_json, f, indent=4, ensure_ascii=False)