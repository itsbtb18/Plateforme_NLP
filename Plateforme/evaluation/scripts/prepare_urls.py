import json
import glob
import random
import os

def prepare_urls():
    valid_urls = []
    # Collect valid URLs from ground_truth
    for file_path in glob.glob("evaluation/ground_truth/*.json"):
        if "urls_to_test" in file_path:
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    url = item.get("source_url") or item.get("url")
                    if url and url not in valid_urls and url.startswith("http"):
                        valid_urls.append(url)
        except Exception:
            pass

    # Pick exactly 25
    random.seed(42)
    selected_valid = random.sample(valid_urls, min(25, len(valid_urls)))

    invalid_urls = [
        "https://httpstat.us/404",
        "https://httpstat.us/500",
        "https://httpstat.us/403",
        "https://www.example.com/does_not_exist_404_test",
        "https://amazon.com/dp/B08N5WRWNW",  # E-commerce
        "https://www.nike.com/t/air-force-1-07", # E-commerce
        "https://en.wikipedia.org/wiki/Baking", # Off-topic wiki
        "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/", # Recipe
        "https://www.imdb.com/title/tt0111161/", # Movie
        "https://www.zillow.com/homes/San-Francisco,-CA_rb/", # Real estate
        "http://thispagedoesnotexist123456789.com", # DNS error
        "https://www.walmart.com/ip/apples", # E-commerce
        "https://httpstat.us/401",
        "https://www.ebay.com/itm/123456",
        "https://en.wikipedia.org/wiki/List_of_dog_breeds",
        "https://www.asos.com/men/",
        "https://www.booking.com/city/fr/paris.html",
        "https://www.tripadvisor.com/Restaurants-g187147-Paris_Ile_de_France.html",
        "https://www.ikea.com/us/en/cat/sofas-fu003/",
        "https://www.homedepot.com/b/Lumber-Composites/N-5yc1vZbqpg",
        "https://www.target.com/c/grocery/-/N-5xt1a",
        "https://www.bestbuy.com/site/tv-home-theater/tvs/abcat0101000.c",
        "https://www.sephora.com/shop/makeup-cosmetics",
        "https://www.healthline.com/nutrition/50-super-healthy-foods",
        "https://en.wikipedia.org/wiki/Coffee"
    ]
    
    # Just in case we didn't hit 25
    while len(invalid_urls) < 25:
        invalid_urls.append(f"https://example.com/invalid_{len(invalid_urls)}")
    invalid_urls = invalid_urls[:25]

    final_data = []
    for u in selected_valid:
        final_data.append({"url": u, "expected_valid": True})
    for u in invalid_urls:
        final_data.append({"url": u, "expected_valid": False})

    out_path = "evaluation/ground_truth/urls_to_test.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2)
    
    print(f"Generated {out_path} with {len(selected_valid)} valid and {len(invalid_urls)} invalid URLs.")

if __name__ == "__main__":
    prepare_urls()
