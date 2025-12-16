from rich import print
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from datetime import datetime
from pydantic import BaseModel
from urllib.parse import urlparse
import json
from typing import Callable, Literal
from pathlib import Path

class LinkData(BaseModel):
    text: str
    href: str

Paper = Literal[
    "thetimes",
    "thesun",
    "express",
    "mirror",
    "telegraph",
    "theguardian",
    "dailymail",
    "ft",
    "metro",
    "independent",
    "observer",
    "dailystar",
]

ai_topic_page_maps: dict[Paper, Callable[[int], str]] = {
    "thetimes": lambda n : f"https://www.thetimes.com/topic/artificial-intelligence?page={n}",
    "thesun": lambda n : f"https://www.thesun.co.uk/topic/artificial-intelligence/page/{n}/",
    "express": lambda n : f"https://www.express.co.uk/latest/artificial-intelligence?pageNumber={n}",
    "mirror": lambda n : f"https://www.mirror.co.uk/all-about/artificial-intelligence?pageNumber={n}",
    "telegraph": lambda n : f"https://www.telegraph.co.uk/artificial-intelligence/page-{n}/",
    "theguardian": lambda n : f"https://www.theguardian.com/technology/artificialintelligenceai?page={n}",
    "dailymail": lambda n : f"https://www.dailymail.co.uk/sciencetech/ai/index.html?page={n}",
    "ft": lambda n : f"https://www.ft.com/artificial-intelligence?page={n}",
    "metro": lambda n : f"https://metro.co.uk/tag/artificial-intelligence/page/{n}/",
    "independent": lambda n : f"https://www.independent.co.uk/topic/ai",
    "observer": lambda n : f"https://observer.co.uk/tags/artificial-intelligence/{20*n}",
    "dailystar": lambda n : f"https://www.dailystar.co.uk/latest/artificial-intelligence?pageNumber={n}",
}

# https://www.thetimes.com/topic/artificial-intelligence?page=2
# https://www.thesun.co.uk/topic/artificial-intelligence/page/2/
# https://www.express.co.uk/latest/artificial-intelligence?pageNumber=2
# https://www.mirror.co.uk/all-about/artificial-intelligence?pageNumber=2
# https://www.telegraph.co.uk/artificial-intelligence/page-2/
# https://www.theguardian.com/technology/artificialintelligenceai?page=2
# https://www.dailymail.co.uk/sciencetech/ai/index.html?page=2
# https://www.ft.com/artificial-intelligence?page=2
# https://metro.co.uk/tag/artificial-intelligence/page/2/
# https://www.independent.co.uk/topic/ai
# https://observer.co.uk/tags/artificial-intelligence/80
# https://www.dailystar.co.uk/latest/artificial-intelligence?pageNumber=2

def setup_driver():
    """Initialize and configure the Chrome WebDriver"""
    options = webdriver.ChromeOptions()
    # Uncomment the next line to run in headless mode (no browser window)
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver

def scrape_body_text(driver: webdriver.Chrome) -> str:
    # Scrape visible text from the body element of the current page
    body = driver.find_element(by=By.CLASS_NAME, value="body")
    return body.text

def scrape_all_links(driver: webdriver.Chrome) -> list[LinkData]:
    links = driver.find_elements(By.XPATH, "//a")
    link_datas = []
    for link in links:
        href = link.get_attribute("href")
        if not href:
            continue
        link_datas.append(
            LinkData(text=link.text, href=href)
        )
    return link_datas

def href_base(href: str) -> str:
    parsed = urlparse(href)
    return parsed.netloc

def collect_links(driver: webdriver.Chrome, url: str):
    """
    Navigate to a news website ai page
    """    
    time.sleep(1)
    
    # Navigate to the initial URL
    print(f"Navigating to {url}...")
    driver.get(url)
    
    time.sleep(2)  # Brief wait for page load
    
    links = scrape_all_links(driver)
    
    # Filter out links that are not to the same webpage
    links = list(filter(lambda link : href_base(link.href) == href_base(url), links))
    return links

def merge_links(old_links:list[LinkData], new_links:list[LinkData]) -> tuple[bool, list[LinkData]]:
    # Merge links by href, and return a bool representing any links were merged
    links = old_links
    old_length = len(old_links)
    for new_link in new_links:
        if new_link.href in [link.href for link in links]:
            continue
        links.append(new_link)
    
    merged = len(links) > old_length
    
    return merged, links
    
def collect_link_scheme(driver: webdriver.Chrome, link_scheme: Callable[[int], str], page_limit = 10):
    # iterate through page numbers while we are getting new links
    links = []
    for n in range(1, page_limit+1):
        new_links = collect_links(driver, link_scheme(n))
        merged, links = merge_links(links, new_links)
        if not merged:
            break
    return links

class SmartLinkScrapeResult(BaseModel):
    schema_links: list[LinkData]
    multiple_links: list[LinkData]
    all_links: list[LinkData]
    once_links: list[LinkData]

def smart_collect_link_scheme(driver: webdriver.Chrome, link_scheme: Callable[[int], str], page_limit = 10):
    # iterate through page numbers while we are getting new links
    # maintain the history of all scraped links
    links:list[LinkData] = []
    scrape_history:list[list[LinkData]] = []
    for n in range(1, page_limit+1):
        new_links = collect_links(driver, link_scheme(n))
        merged, links = merge_links(links, new_links)
        if not merged:
            break
        scrape_history.append(new_links)
    # we can reject the links matching our link scheme (this matches sub and superstrings too)
    def matches_scheme(href:str, n:int):
        for i in range(1,n+1):
            if href in link_scheme(i) or link_scheme(i) in href:
                return True
        return False
    # we can reject links that appear on all pages
    # we can mark links that appear on multiple but not all pages for testing
    def count_scrapes(href:str, scrape_history:list[list[LinkData]]):
        total = 0 
        for scrape in scrape_history:
            if href in [link.href for link in scrape]:
                total += 1
        return total
    schema_links = list(filter(lambda link: matches_scheme(link.href, len(scrape_history)+5), links))
    links = list(filter(lambda link: not matches_scheme(link.href, len(scrape_history)+5), links))
    
    once_scraped_links = list(filter(lambda link: count_scrapes(link.href, scrape_history) == 1, links))
    multiple_scraped_links = list(filter(lambda link: 1 < count_scrapes(link.href, scrape_history) < len(scrape_history), links))
    always_scraped_links = list(filter(lambda link: count_scrapes(link.href, scrape_history) == len(scrape_history), links))
    return SmartLinkScrapeResult(
        schema_links=schema_links, 
        all_links=always_scraped_links, 
        multiple_links=multiple_scraped_links, 
        once_links=once_scraped_links
    )

def write_link_scrape(slsr: SmartLinkScrapeResult, filename: str):
    path = Path("scrapes/links") / filename
    with open(path, "w") as outfile:
        outfile.write(
            slsr.model_dump_json(indent=4)
        )

def read_link_scrape(filename: str) -> SmartLinkScrapeResult:
    path = Path("scrapes/links") / filename
    with open(path, "r") as outfile:
        contents = outfile.read()
    slsr = SmartLinkScrapeResult.model_validate_json(contents)
    return slsr

def scrape_filename(paper: Paper, page_limit: int, date=None) -> str:
    if date is None:
        date = datetime.now().date().isoformat()
    return f"scrape-{paper}-{page_limit}-pages-{date}.json"

if __name__ == "__main__":
    driver = setup_driver()
    # Collect links from a webpage
    # url = ai_topic_page_maps["express"](2)
    # links = collect_links(driver, url)
    
    # Collect paginated links from a scheme
    # url_scheme = ai_topic_page_maps["express"]
    # links = collect_link_scheme(driver, url_scheme, page_limit=10)
    # with open("collected_links.json", "w") as outfile:
    #     links = list([link.model_dump() for link in links])
    #     json.dump(links, outfile, indent=4)
        
    # Collect paginated links with some more link filtering
    # url_scheme = ai_topic_page_maps["express"]
    
    PAPER = "ft"
    PAGE_LIMIT = 4
    url_scheme = ai_topic_page_maps["ft"]
    scrape_result= smart_collect_link_scheme(driver, url_scheme, page_limit=4)
    print(
        "Schema:" + "-"*30,
        scrape_result.schema_links, 
        "Every page:" + "-"*30,
        scrape_result.all_links, 
        "Multiple pages:" + "-"*30,
        scrape_result.multiple_links,
    )
    
    write_link_scrape(scrape_result, scrape_filename(paper=PAPER, page_limit=PAGE_LIMIT))
    
    slsr = read_link_scrape(scrape_filename(paper=PAPER, page_limit=PAGE_LIMIT))
    
    print(slsr)