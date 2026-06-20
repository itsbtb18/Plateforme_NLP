import json
import os
import glob
import re
from dateutil import parser

def parse_to_iso(val):
    if not val or not isinstance(val, str):
        return val
    
    val_strip = val.strip()
    if not val_strip or val_strip.lower() in ["none", "null", "n/a"]:
        return val
    
    # Already ISO strict?
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val_strip):
        return val_strip
        
    # Year only?
    if re.match(r"^\d{4}$", val_strip):
        return f"{val_strip}-01-01"
        
    # Year-Month?
    if re.match(r"^\d{4}-\d{2}$", val_strip):
        return f"{val_strip}-01"
    
    # Try parsing
    try:
        # Check if it contains at least one digit to avoid parsing plain words as dates
        if not any(char.isdigit() for char in val_strip):
            return val
            
        dt = parser.parse(val_strip)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # Fallback for "Month Year"
        try:
             dt = parser.parse(f"01 {val_strip}")
             return dt.strftime("%Y-%m-%d")
        except:
             return val

def normalize_ground_truth():
    gt_files = glob.glob("evaluation/ground_truth/*.json")
    # Extended list of common date keywords
    date_keywords = [
        "date", "deadline", "published", "submission", 
        "notification", "start", "end", "application", "created"
    ]
    
    total_conversions = 0
    
    for file_path in gt_files:
        if "urls_to_test" in file_path: continue
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        conversions_in_file = 0
        for item in data:
            for k, v in item.items():
                # Check if key name suggests a date OR value looks like a non-ISO date
                is_date_field = any(kw in k.lower() for kw in date_keywords)
                if is_date_field and isinstance(v, str):
                    new_val = parse_to_iso(v)
                    if new_val != v:
                        item[k] = new_val
                        conversions_in_file += 1
                        total_conversions += 1
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"File: {os.path.basename(file_path)} | {conversions_in_file} dates normalized")
        
    print(f"\nTotal: {total_conversions} dates normalized across all files.")

if __name__ == "__main__":
    normalize_ground_truth()
