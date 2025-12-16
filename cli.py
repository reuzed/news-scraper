import typer
from collect_links import setup_driver, smart_collect_link_scheme, Paper, ai_topic_page_maps, write_link_scrape, link_scrape_filename
from utils import glob_articles, glob_links, PAPERS
app = typer.Typer(help="News website scraping app using Selenium. Collect links, process these then scrape them.")

@app.command()
def collect_links(
    paper: Paper,
    page_limit: int = typer.Option(10, help="Maximum number of pages to try to scrape for links."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Collect links for a newspaper's artticles on ai"""
    driver = setup_driver()
    link_scheme = ai_topic_page_maps[paper]
    links = smart_collect_link_scheme(driver, link_scheme, page_limit)
    if verbose:
        print(
            f"{len(links.all_links)} links appear on all pages, eg. {links.all_links[:5]}...", 
            f"{len(links.multiple_links)} links appear on multiple pages, eg. {links.multiple_links[:5]}...", 
            f"{len(links.once_links)} links appear on one page, eg. {links.once_links[:5]}...", 
            f"{len(links.schema_links)} links match our page finding schema, eg. {links.schema_links[:5]}...",
        )
    write_link_scrape(links, link_scrape_filename(paper, page_limit))

@app.command()
def batch_collect_papers(page_limit: int = typer.Option(10, help="Maximum number of pages to try to scrape for links.")):
    """From each paper in the list, scrape links to articles, and save """
    driver = setup_driver()
    for paper in PAPERS:
        print(f"Scraping {paper}".center(80, "—"))
        link_scheme = ai_topic_page_maps[paper]
        links = smart_collect_link_scheme(driver, link_scheme, page_limit)
        print(f"Found {len(links.once_links)} probable article links.")
        write_link_scrape(links, link_scrape_filename(paper, page_limit))

@app.command()
def list_link_scrapes(
        paper:Paper|None = typer.Option(None, help="Filter to only scrapes of the particular paper.")
    ):
    """List link scrapes from the directory, optionally filtering by paper"""
    return glob_links(paper=paper)

@app.command()
def list_article_scrapes():
    return glob_articles()

@app.command()
def archive_scrape_article():
    pass

@app.command()
def list(all: bool = typer.Option(False, "--all", "-a", help="List all items")):
    """List items."""
    print("Listing all..." if all else "Listing...")

if __name__ == "__main__":
    app()