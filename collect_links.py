from rich import print
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from pydantic import BaseModel

# ai_topic_pages = [
#     "https://www.thetimes.com/topic/artificial-intelligence",
#     "https://www.thesun.co.uk/topic/artificial-intelligence/",
#     "https://www.express.co.uk/latest/artificial-intelligence",
#     "https://www.mirror.co.uk/all-about/artificial-intelligence",
# ]

ai_topic_page_maps = {
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

def find_archive_page_link(driver: webdriver.Chrome) -> str:
    # When we are on archive.md page, we want to click the archive link to get to our article
    links = driver.find_elements(By.XPATH, "//a[contains(@href, 'archive.md')]")
        
    if len(links) == 0:
        time.sleep(10)
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'archive.md')]")
    
    # All the bad archive links have a webpage after https://archive.md, we can find this by looking for a . after md
    link_texts = list(map(lambda l: l.get_attribute('href'), links))
    # print("found", len(links), "links", link_texts)

    good_link_texts = list(filter(lambda lt: '.' not in lt.split("md")[1], link_texts)) # type: ignore
    good_link_text = good_link_texts[0]
    # print("good links", len(good_link_texts), good_link_text)
    if good_link_text is None:
        print()
        raise ValueError("No link found")
    return good_link_text

def scrape_website(driver: webdriver.Chrome, url: str, captcha_wait_time=60) -> str:
    """
    Navigate to a website, click a link, wait for CAPTCHA, and scrape body text
    
    Args:
        url: The initial URL to visit
        captcha_wait_time: Maximum time to wait for CAPTCHA completion (seconds)
    
    Returns:
        The scraped body text as a string
    """    
    time.sleep(1)
    
    # Navigate to the initial URL
    print(f"Navigating to {url}...")
    driver.get(url)
    
    WebDriverWait(driver, captcha_wait_time).until(
        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'archive.md')]"))
    )
    
    time.sleep(2)  # Brief wait for page load
    
    good_link_text = find_archive_page_link(driver)
    
    # Go to archived page
    print(f"Navigating to {good_link_text}...")
    driver.get(good_link_text)
    
    time.sleep(2) # Wait for page load again
    
    # Scrape the body text
    print("Scraping body text...")
    body_text = scrape_body_text(driver)
    
    print(f"Scraped {len(body_text)} characters.")
    return body_text
  