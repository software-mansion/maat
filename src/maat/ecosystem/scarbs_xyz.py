import re
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://scarbs.xyz/"


def fetch_all_packages() -> Iterable[str]:
    response = requests.get(urljoin(BASE_URL, "/packages"))
    soup = BeautifulSoup(response.text, "html.parser")

    total_pages = 1
    for link in soup.select("a[href*='?page=']"):
        href = link.get("href")
        match = re.match(r".*page=(\d+).*", href)
        if match:
            page_number = int(match.group(1))
            total_pages = max(total_pages, page_number)

    for page in range(1, total_pages + 1):
        page_url = urljoin(BASE_URL, f"/packages?page={page}")
        yield from _get_packages_from_page(page_url)


def _get_packages_from_page(page_url):
    response = requests.get(page_url)
    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.select("a[href*='/packages/']"):
        href = link.get("href")
        match = re.match(r".*/packages/([^/]+)(?:$|/.*)", href)
        if match:
            yield match.group(1)
