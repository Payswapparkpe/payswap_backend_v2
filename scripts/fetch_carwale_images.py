#!/usr/bin/env python3
"""
Fetch car images from CarWale (https://www.carwale.com/images/) and save them
to the backend project under Image Files/car image/.

Usage:
  python scripts/fetch_carwale_images.py [--max-pages N] [--max-cars N] [--max-per-car N]
  Omit limits to fetch all (can be slow and heavy).
"""

import argparse
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.carwale.com"
LISTING_URL = "https://www.carwale.com/images/"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "Image Files" / "car image"

# Match car gallery links: /brand-cars/model/images/ or /brand-cars/model/images
CAR_GALLERY_PATTERN = re.compile(r"^/([^/]+-cars/[^/]+)/images/?$")

# CarWale CDN; exclude placeholders
IMAGE_CDN = "imgd.aeplcdn.com"
PLACEHOLDER_PATTERN = re.compile(r"statics/grey|\.svg\b", re.I)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def slug_to_folder_name(slug: str) -> str:
    """Convert URL slug like 'tata-cars/punch' to a safe folder name."""
    # Use only the path part; replace - and / with space then clean
    name = slug.replace("-", " ").replace("/", " ")
    # Remove extra spaces and strip
    name = " ".join(name.split())
    return name or slug.replace("/", "-")


def get_car_gallery_links(max_pages: int | None) -> list[tuple[str, str]]:
    """Fetch main listing (and optional pagination) and return (slug, name) for each car gallery."""
    seen = set()
    results = []
    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            break
        url = LISTING_URL if page == 1 else f"{LISTING_URL}page/{page}/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href or (not href.startswith("/") and "carwale.com" not in href):
                continue
            # Normalize to path: remove scheme/host and query
            path = href.split("?")[0].rstrip("/")
            if "carwale.com" in path:
                path = "/" + path.split("carwale.com", 1)[-1].lstrip("/")
            if not path.endswith("/images"):
                continue
            path = path[:-7] if path.endswith("/images") else path  # remove '/images'
            m = re.match(r"^/([^/]+-cars/[^/]+)$", path)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            name = slug_to_folder_name(slug)
            results.append((slug, name))
        # Next page
        next_links = soup.find_all("a", href=re.compile(r"^/images/page/\d+/"))
        if not next_links or page >= (max_pages or 999):
            break
        page += 1
        time.sleep(0.5)
    return results


def get_image_urls_from_gallery(gallery_url: str) -> list[str]:
    """Fetch a car's image gallery page and return list of image URLs (imgd.aeplcdn.com)."""
    try:
        r = requests.get(gallery_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Error fetching gallery {gallery_url}: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    for img in soup.find_all("img", src=True):
        src = img["src"].strip()
        if IMAGE_CDN not in src or PLACEHOLDER_PATTERN.search(src):
            continue
        if "data-src" in img.attrs and img["data-src"]:
            src = img["data-src"].strip()
        if IMAGE_CDN not in src or PLACEHOLDER_PATTERN.search(src):
            continue
        if not src.startswith("http"):
            src = "https:" + src if src.startswith("//") else "https://" + src
        urls.append(src)
    # Also check for data-src in other tags (lazy load)
    for tag in soup.find_all(attrs={"data-src": True}):
        src = tag.get("data-src", "").strip()
        if IMAGE_CDN in src and not PLACEHOLDER_PATTERN.search(src):
            if not src.startswith("http"):
                src = "https:" + src if src.startswith("//") else "https://" + src
            urls.append(src)
    return list(dict.fromkeys(urls))  # dedupe order-preserving


def download_image(url: str, dest_path: Path) -> bool:
    """Download a single image to dest_path. Returns True on success."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        r.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    Download failed {url[:60]}...: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch CarWale car images into Image Files/car image/")
    parser.add_argument("--max-pages", type=int, default=2, help="Max listing pages to scrape (default 2)")
    parser.add_argument("--max-cars", type=int, default=5, help="Max cars to process (default 5)")
    parser.add_argument("--max-per-car", type=int, default=20, help="Max images per car (default 20)")
    parser.add_argument("--no-limit", action="store_true", help="No limits (fetch all; can be very slow)")
    args = parser.parse_args()

    max_pages = None if args.no_limit else args.max_pages
    max_cars = None if args.no_limit else args.max_cars
    max_per_car = None if args.no_limit else args.max_per_car

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print("Fetching car gallery links...")
    cars = get_car_gallery_links(max_pages)
    if max_cars is not None:
        cars = cars[:max_cars]
    print(f"Found {len(cars)} car galleries to process.")

    total_downloaded = 0
    for slug, name in cars:
        gallery_url = f"{BASE_URL}/{slug}/images/"
        print(f"\n{name} ({slug})")
        urls = get_image_urls_from_gallery(gallery_url)
        if max_per_car is not None:
            urls = urls[:max_per_car]
        print(f"  Images found: {len(urls)}")
        car_dir = OUTPUT_DIR / slug_to_folder_name(slug)
        for i, url in enumerate(urls, 1):
            ext = "png"
            if ".jpg" in url.lower() or "jpeg" in url.lower():
                ext = "jpg"
            dest = car_dir / f"{i:04d}.{ext}"
            if download_image(url, dest):
                total_downloaded += 1
            time.sleep(0.2)
    print(f"\nDone. Total images saved: {total_downloaded} in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
