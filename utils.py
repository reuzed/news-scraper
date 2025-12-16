from urllib.parse import urlparse
import re
from pathlib import Path
from typing import Callable, Literal, get_args
from pydantic import BaseModel
from pydantic import TypeAdapter
from datetime import datetime

LINK_SCRAPE_DIR = Path("scrapes/links/raw")
CLEAN_LINK_SCRAPE_DIR = Path("scrapes/links/clean")
ARTICLE_SCRAPE_DIR = Path("scrapes/articles/raw")
CLEAN_ARTICLE_SCRAPE_DIR = Path("scrapes/articles/clean")

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

PAPERS:list[Paper] = list(get_args(Paper))

LinkScheme = Callable[[int], str]

ai_topic_page_maps: dict[Paper, LinkScheme] = {
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

class LinkData(BaseModel):
    text: str
    href: str

class SmartLinkScrapeResult(BaseModel):
    once_links: list[LinkData]
    schema_links: list[LinkData]
    multiple_links: list[LinkData]
    all_links: list[LinkData]

class ScrapeData(BaseModel):
    url: str
    content: str
    
class Scrape(ScrapeData):
    success: bool

def glob_articles():
    articles_dir = Path("scrapes/articles")
    article_paths = list(articles_dir.rglob("*.json"))
    return article_paths

def glob_links(paper:Paper|None=None):
    links_dir = Path("scrapes/links")
    links_paths = list(links_dir.rglob("*.json"))
    if paper is not None:
        links_paths = list(filter(lambda lp : f"-{paper}-" in str(lp), links_paths))
    return links_paths

def write_link_scrape(slsr: SmartLinkScrapeResult, filename: str):
    path = LINK_SCRAPE_DIR / filename
    with open(path, "w") as outfile:
        outfile.write(
            slsr.model_dump_json(indent=4)
        )

def read_link_scrape(filename: str) -> SmartLinkScrapeResult:
    path = LINK_SCRAPE_DIR / filename
    with open(path, "r") as outfile:
        contents = outfile.read()
    slsr = SmartLinkScrapeResult.model_validate_json(contents)
    return slsr

LinkDataList = TypeAdapter(list[LinkData])

def write_clean_link_scrape(links: list[LinkData], filename: str):
    path = CLEAN_LINK_SCRAPE_DIR / filename
    with open(path, "w") as outfile:
        outfile.write(LinkDataList.dump_json(links, indent=4).decode())

def read_clean_link_scrape(filename: str) -> list[LinkData]:
    path = CLEAN_LINK_SCRAPE_DIR / filename
    with open(path, "r") as outfile:
        contents = outfile.read()
    return LinkDataList.validate_json(contents)

def link_scrape_filename(paper: Paper, page_limit: int, batch_id=None) -> str:
    if batch_id is None:
        batch_id = datetime.now().date().isoformat()
    return f"scrape-{paper}-{page_limit}-pages-{batch_id}.json"

def write_article_scrape(scrape: Scrape, filename: str):
    path = ARTICLE_SCRAPE_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(scrape.model_dump_json(indent=2))

def read_article_scrape(filename: str) -> Scrape:
    path = ARTICLE_SCRAPE_DIR / filename
    with open(path, "r") as f:
        return Scrape.model_validate_json(f.read())

def write_clean_article_scrape(scrape: ScrapeData, filename: str):
    path = CLEAN_ARTICLE_SCRAPE_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(scrape.model_dump_json(indent=2))

def read_clean_article_scrape(filename: str) -> ScrapeData:
    path = CLEAN_ARTICLE_SCRAPE_DIR / filename
    with open(path, "r") as f:
        return ScrapeData.model_validate_json(f.read())

def article_scrape_filename(paper: Paper, href: str, batch_id: str | None = None) -> str:
    if batch_id is None:
        batch_id = datetime.now().date().isoformat()
    
    # Extract path from href and sanitize
    parsed = urlparse(href)
    slug = parsed.path.strip("/").replace("/", "-")
    slug = re.sub(r"[^\w\-]", "", slug)  # Remove non-alphanumeric chars
    slug = slug[:80]  # Truncate if too long
    
    return f"{paper}-{slug}-{batch_id}.json"