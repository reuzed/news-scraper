from rich import print
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from urllib.parse import urlparse
from utils import LinkData, SmartLinkScrapeResult, Paper, LinkScheme, write_link_scrape, read_link_scrape, link_scrape_filename

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
    
def collect_link_scheme(driver: webdriver.Chrome, link_scheme: LinkScheme, page_limit = 10):
    # iterate through page numbers while we are getting new links
    links = []
    for n in range(1, page_limit+1):
        new_links = collect_links(driver, link_scheme(n))
        merged, links = merge_links(links, new_links)
        if not merged:
            break
    return links

def smart_collect_link_scheme(driver: webdriver.Chrome, link_scheme: LinkScheme, page_limit = 10):
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
    from utils import ai_topic_page_maps
    PAPER:Paper = "ft"
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
    
    write_link_scrape(scrape_result, link_scrape_filename(paper=PAPER, page_limit=PAGE_LIMIT))
    
    slsr = read_link_scrape(link_scrape_filename(paper=PAPER, page_limit=PAGE_LIMIT))
    
    print(slsr)