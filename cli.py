import typer
from pathlib import Path
from rich import print as rprint
from collect_links import setup_driver, smart_collect_link_scheme, ai_topic_page_maps
from utils import (
    glob_articles, glob_links, PAPERS, Paper, get_batch_id, parse_link_scrape_filename,
    parse_article_scrape_filename, clean_link_scrape_exists, article_scrape_exists,
    clean_article_scrape_exists, get_link_scrapes_for_batch, get_clean_link_scrapes_for_batch,
    get_article_scrapes_for_batch, get_clean_article_scrapes_for_batch,
    read_link_scrape, write_clean_link_scrape, read_clean_link_scrape,
    read_article_scrape, write_article_scrape, write_clean_article_scrape,
    read_clean_article_scrape, article_scrape_filename, link_scrape_filename,
    write_link_scrape, LINK_SCRAPE_DIR,
    CLEAN_LINK_SCRAPE_DIR, ARTICLE_SCRAPE_DIR, CLEAN_ARTICLE_SCRAPE_DIR
)
from llm import filter_links, extract_article_text
from scrape_from_archive import scrape_from_archive, setup_driver as setup_archive_driver
from typing import Optional

app = typer.Typer(help="News website scraping app using Selenium. Collect links, process these then scrape them.")

# Internal helper functions (not CLI commands)
def _batch_clean_links_impl(batch_id: str, force: bool = False):
    """Internal implementation of batch_clean_links"""
    rprint(f"[blue]Processing batch: {batch_id}[/blue]")
    
    # Get all link scrapes for this batch
    link_scrapes = get_link_scrapes_for_batch(batch_id)
    if not link_scrapes:
        rprint(f"[yellow]No link scrapes found for batch {batch_id}[/yellow]")
        return
    
    rprint(f"[blue]Found {len(link_scrapes)} link scrapes to process[/blue]")
    
    # Get already cleaned scrapes
    if not force:
        cleaned_scrapes = {p.name for p in get_clean_link_scrapes_for_batch(batch_id)}
        link_scrapes = [p for p in link_scrapes if p.name not in cleaned_scrapes]
        if cleaned_scrapes:
            rprint(f"[yellow]Skipping {len(cleaned_scrapes)} already cleaned scrapes. Use --force to re-clean.[/yellow]")
    
    if not link_scrapes:
        rprint(f"[green]All link scrapes already cleaned for batch {batch_id}[/green]")
        return
    
    # Process each link scrape
    success_count = 0
    error_count = 0
    
    for link_scrape_path in link_scrapes:
        filename = link_scrape_path.name
        paper, page_limit, _ = parse_link_scrape_filename(filename)
        
        rprint(f"[cyan]Cleaning links for {paper} (page_limit={page_limit})...[/cyan]")
        try:
            scrape_result = read_link_scrape(filename)
            filtered_links = filter_links(scrape_result)
            write_clean_link_scrape(filtered_links, filename)
            rprint(f"[green]✓ Cleaned {len(filtered_links)} links for {paper}[/green]")
            success_count += 1
        except Exception as e:
            rprint(f"[red]✗ Error cleaning links for {paper}: {e}[/red]")
            error_count += 1
            # Continue with next scrape instead of failing completely
    
    rprint(f"\n[blue]Batch cleaning complete: {success_count} succeeded, {error_count} failed[/blue]")

def _batch_archive_scrape_articles_impl(batch_id: str, force: bool = False, article_limit: int | None = None):
    """Internal implementation of batch_archive_scrape_articles
    
    Args:
        batch_id: Batch ID to process
        force: Force re-scraping even if files exist
        article_limit: Limit number of articles to scrape per paper (None = no limit)
    """
    rprint(f"[blue]Processing batch: {batch_id}[/blue]")
    if article_limit:
        rprint(f"[blue]Limiting to {article_limit} articles per paper[/blue]")
    
    # Get all clean link scrapes for this batch
    clean_link_scrapes = get_clean_link_scrapes_for_batch(batch_id)
    if not clean_link_scrapes:
        rprint(f"[yellow]No clean link scrapes found for batch {batch_id}. Run batch_clean_links first.[/yellow]")
        return
    
    rprint(f"[blue]Found {len(clean_link_scrapes)} clean link scrapes[/blue]")
    
    # Collect all links to scrape, limiting per paper if requested
    all_links_to_scrape: list[tuple[Paper, str]] = []
    for clean_link_path in clean_link_scrapes:
        filename = clean_link_path.name
        paper, _, _ = parse_link_scrape_filename(filename)
        if paper is None:
            continue
        
        try:
            clean_links = read_clean_link_scrape(filename)
            paper_count = 0
            for link in clean_links:
                # Apply per-paper limit if specified
                if article_limit and paper_count >= article_limit:
                    rprint(f"[yellow]Reached limit of {article_limit} articles for {paper}, skipping remaining[/yellow]")
                    break
                
                article_filename = article_scrape_filename(paper, link.href, batch_id=batch_id)
                if force or not article_scrape_exists(article_filename):
                    all_links_to_scrape.append((paper, link.href))
                    paper_count += 1
        except Exception as e:
            rprint(f"[red]Error reading clean links from {filename}: {e}[/red]")
            continue
    
    if not all_links_to_scrape:
        rprint(f"[green]All articles already scraped for batch {batch_id}[/green]")
        return
    
    rprint(f"[blue]Found {len(all_links_to_scrape)} articles to scrape[/blue]")
    
    # Setup driver once for batch
    driver = setup_archive_driver()
    success_count = 0
    error_count = 0
    
    try:
        for i, (paper, url) in enumerate(all_links_to_scrape, 1):
            filename = article_scrape_filename(paper, url, batch_id=batch_id)
            rprint(f"[cyan][{i}/{len(all_links_to_scrape)}] Scraping {paper}: {url[:60]}...[/cyan]")
            
            try:
                scrapes = scrape_from_archive(driver, url)
                
                if scrapes and scrapes[0].success:
                    write_article_scrape(scrapes[0], filename)
                    rprint(f"[green]✓ Successfully scraped ({len(scrapes[0].content)} chars)[/green]")
                    success_count += 1
                else:
                    rprint(f"[red]✗ Failed to scrape[/red]")
                    # Save failed scrape
                    if scrapes:
                        write_article_scrape(scrapes[0], filename)
                    error_count += 1
            except Exception as e:
                rprint(f"[red]✗ Error scraping {url}: {e}[/red]")
                # Save failed scrape
                from utils import Scrape
                failed_scrape = Scrape(url=url, content="", success=False)
                write_article_scrape(failed_scrape, filename)
                error_count += 1
                # Continue with next article instead of failing completely
    finally:
        driver.quit()
    
    rprint(f"\n[blue]Batch scraping complete: {success_count} succeeded, {error_count} failed[/blue]")

def _batch_clean_articles_impl(batch_id: str, force: bool = False):
    """Internal implementation of batch_clean_articles"""
    rprint(f"[blue]Processing batch: {batch_id}[/blue]")
    
    # Get all article scrapes for this batch
    article_scrapes = get_article_scrapes_for_batch(batch_id)
    if not article_scrapes:
        rprint(f"[yellow]No article scrapes found for batch {batch_id}[/yellow]")
        return
    
    rprint(f"[blue]Found {len(article_scrapes)} article scrapes to process[/blue]")
    
    # Get already cleaned articles
    if not force:
        cleaned_articles = {p.name for p in get_clean_article_scrapes_for_batch(batch_id)}
        article_scrapes = [p for p in article_scrapes if p.name not in cleaned_articles]
        if cleaned_articles:
            rprint(f"[yellow]Skipping {len(cleaned_articles)} already cleaned articles. Use --force to re-clean.[/yellow]")
    
    if not article_scrapes:
        rprint(f"[green]All articles already cleaned for batch {batch_id}[/green]")
        return
    
    # Process each article scrape
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for article_scrape_path in article_scrapes:
        filename = article_scrape_path.name
        
        try:
            scrape = read_article_scrape(filename)
            
            if not scrape.success:
                rprint(f"[yellow]Skipping failed scrape: {filename}[/yellow]")
                skipped_count += 1
                continue
            
            if not scrape.content:
                rprint(f"[yellow]Skipping empty scrape: {filename}[/yellow]")
                skipped_count += 1
                continue
            
            rprint(f"[cyan]Cleaning article: {filename}...[/cyan]")
            cleaned_content = extract_article_text(scrape.content)
            
            from utils import ScrapeData
            clean_scrape = ScrapeData(url=scrape.url, content=cleaned_content)
            write_clean_article_scrape(clean_scrape, filename)
            
            rprint(f"[green]✓ Cleaned article ({len(cleaned_content)} chars)[/green]")
            success_count += 1
        except Exception as e:
            rprint(f"[red]✗ Error cleaning article {filename}: {e}[/red]")
            error_count += 1
            # Continue with next article instead of failing completely
    
    rprint(f"\n[blue]Batch cleaning complete: {success_count} succeeded, {error_count} failed, {skipped_count} skipped[/blue]")

def _batch_collect_papers_impl(page_limit: int, batch_id: str):
    """Internal implementation of batch_collect_papers"""
    driver = setup_driver()
    try:
        for paper in PAPERS:
            rprint(f"[cyan]Collecting links for {paper}...[/cyan]")
            try:
                link_scheme = ai_topic_page_maps[paper]
                links = smart_collect_link_scheme(driver, link_scheme, page_limit)
                write_link_scrape(links, link_scrape_filename(paper, page_limit, batch_id=batch_id))
                rprint(f"[green]✓ Collected {len(links.once_links)} links for {paper}[/green]")
            except Exception as e:
                rprint(f"[red]✗ Error collecting links for {paper}: {e}[/red]")
                # Continue with next paper
    finally:
        driver.quit()

@app.command()
def collect_links(
    paper: Paper,
    page_limit: int = typer.Option(10, help="Maximum number of pages to try to scrape for links."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    batch_id: str|None = typer.Option(None, "-b", "--batch-id"),
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
    write_link_scrape(links, link_scrape_filename(paper, page_limit, batch_id=batch_id))

@app.command()
def batch_collect_papers(
    page_limit: int = typer.Option(10, help="Maximum number of pages to try to scrape for links."),
    batch_id: str|None = typer.Option(None, "-b", "--batch-id"),
):
    """From each paper in the list, scrape links to articles, and save """
    batch_id = get_batch_id(batch_id)
    _batch_collect_papers_impl(page_limit, batch_id)

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
def clean_links(
    filename: str = typer.Argument(..., help="Filename of the link scrape to clean"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-cleaning even if clean file exists"),
):
    """Clean the links from a link scrape, and save the cleaned links to /clean"""
    # Check if clean file already exists
    if not force and clean_link_scrape_exists(filename):
        rprint(f"[yellow]Clean link scrape already exists: {filename}. Use --force to re-clean.[/yellow]")
        return
    
    # Read the raw link scrape
    try:
        scrape_result = read_link_scrape(filename)
    except Exception as e:
        rprint(f"[red]Error reading link scrape {filename}: {e}[/red]")
        raise typer.Exit(1)
    
    # Filter links using LLM
    rprint(f"[blue]Filtering {len(scrape_result.once_links) + len(scrape_result.multiple_links)} links with LLM...[/blue]")
    try:
        filtered_links = filter_links(scrape_result)
        rprint(f"[green]Filtered to {len(filtered_links)} article links[/green]")
    except Exception as e:
        rprint(f"[red]Error filtering links with LLM: {e}[/red]")
        raise typer.Exit(1)
    
    # Write cleaned links
    try:
        write_clean_link_scrape(filtered_links, filename)
        rprint(f"[green]Saved cleaned links to {CLEAN_LINK_SCRAPE_DIR / filename}[/green]")
    except Exception as e:
        rprint(f"[red]Error writing clean link scrape: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def batch_clean_links(
    batch_id: str | None = typer.Option(None, "-b", "--batch-id", help="Batch ID to process (defaults to today's date)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-cleaning even if clean files exist"),
):
    """Batch clean the links from several link scrapes, and save these to their respective places in /clean"""
    batch_id = get_batch_id(batch_id)
    _batch_clean_links_impl(batch_id, force)

@app.command()
def clean_articles(
    filename: str = typer.Argument(..., help="Filename of the article scrape to clean"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-cleaning even if clean file exists"),
):
    """Clean an article's text and save to /clean"""
    # Check if clean file already exists
    if not force and clean_article_scrape_exists(filename):
        rprint(f"[yellow]Clean article already exists: {filename}. Use --force to re-clean.[/yellow]")
        return
    
    # Read the raw article scrape
    try:
        scrape = read_article_scrape(filename)
    except Exception as e:
        rprint(f"[red]Error reading article scrape {filename}: {e}[/red]")
        raise typer.Exit(1)
    
    if not scrape.success:
        rprint(f"[yellow]Skipping failed scrape: {filename}[/yellow]")
        return
    
    if not scrape.content:
        rprint(f"[yellow]Skipping empty scrape: {filename}[/yellow]")
        return
    
    # Clean article text using LLM
    rprint(f"[blue]Cleaning article text ({len(scrape.content)} chars)...[/blue]")
    try:
        cleaned_content = extract_article_text(scrape.content)
        rprint(f"[green]Cleaned to {len(cleaned_content)} chars[/green]")
    except Exception as e:
        rprint(f"[red]Error cleaning article with LLM: {e}[/red]")
        raise typer.Exit(1)
    
    # Write cleaned article
    try:
        from utils import ScrapeData
        clean_scrape = ScrapeData(url=scrape.url, content=cleaned_content)
        write_clean_article_scrape(clean_scrape, filename)
        rprint(f"[green]Saved cleaned article to {CLEAN_ARTICLE_SCRAPE_DIR / filename}[/green]")
    except Exception as e:
        rprint(f"[red]Error writing clean article scrape: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def batch_clean_articles(
    batch_id: str | None = typer.Option(None, "-b", "--batch-id", help="Batch ID to process (defaults to today's date)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-cleaning even if clean files exist"),
):
    """Batch clean article contents"""
    batch_id = get_batch_id(batch_id)
    _batch_clean_articles_impl(batch_id, force)

@app.command()
def archive_scrape_article(
    url: str = typer.Argument(..., help="URL of the article to scrape"),
    paper: Paper = typer.Option(..., "-p", "--paper", help="Paper name for filename"),
    batch_id: str | None = typer.Option(None, "-b", "--batch-id", help="Batch ID (defaults to today's date)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-scraping even if file exists"),
):
    """Scrape a single article from archive"""
    batch_id = get_batch_id(batch_id)
    filename = article_scrape_filename(paper, url, batch_id=batch_id)
    
    # Check if already scraped
    if not force and article_scrape_exists(filename):
        rprint(f"[yellow]Article already scraped: {filename}. Use --force to re-scrape.[/yellow]")
        return
    
    # Scrape from archive
    driver = setup_archive_driver()
    try:
        rprint(f"[blue]Scraping {url}...[/blue]")
        scrapes = scrape_from_archive(driver, url)
        
        if scrapes and scrapes[0].success:
            write_article_scrape(scrapes[0], filename)
            rprint(f"[green]✓ Successfully scraped article ({len(scrapes[0].content)} chars)[/green]")
        else:
            rprint(f"[red]✗ Failed to scrape article[/red]")
            # Still save the failed scrape for tracking
            if scrapes:
                write_article_scrape(scrapes[0], filename)
    except Exception as e:
        rprint(f"[red]Error scraping article: {e}[/red]")
        # Save failed scrape
        from utils import Scrape
        failed_scrape = Scrape(url=url, content="", success=False)
        write_article_scrape(failed_scrape, filename)
        raise typer.Exit(1)
    finally:
        driver.quit()

@app.command()
def batch_archive_scrape_articles(
    batch_id: str | None = typer.Option(None, "-b", "--batch-id", help="Batch ID to process (defaults to today's date)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-scraping even if files exist"),
    article_limit: int | None = typer.Option(None, "--article-limit", "-a", help="Limit number of articles to scrape per paper (useful for testing)"),
):
    """In a batch process, scrape the links from archive"""
    batch_id = get_batch_id(batch_id)
    _batch_archive_scrape_articles_impl(batch_id, force, article_limit)

@app.command()
def run_batch(
    page_limit: int = typer.Option(10, help="Maximum number of pages to try to scrape for links."),
    batch_id: str | None = typer.Option(None, "-b", "--batch-id", help="Batch ID to process (defaults to today's date)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-processing even if files exist"),
    article_limit: int | None = typer.Option(None, "--article-limit", "-a", help="Limit number of articles to scrape per paper (useful for testing)"),
    skip_collect: bool = typer.Option(False, "--skip-collect", help="Skip link collection step"),
    skip_clean_links: bool = typer.Option(False, "--skip-clean-links", help="Skip link cleaning step"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Skip article scraping step"),
    skip_clean_articles: bool = typer.Option(False, "--skip-clean-articles", help="Skip article cleaning step"),
):
    """Run the complete batch pipeline: collect links, clean links, scrape articles, clean articles"""
    batch_id = get_batch_id(batch_id)
    rprint(f"[bold blue]Starting batch pipeline for batch_id: {batch_id}[/bold blue]")
    if page_limit != 10:
        rprint(f"[blue]Page limit: {page_limit}[/blue]")
    if article_limit:
        rprint(f"[blue]Article limit per paper: {article_limit}[/blue]")
    
    # Step 1: Collect links
    if not skip_collect:
        rprint(f"\n[bold yellow]Step 1/4: Collecting links from papers...[/bold yellow]")
        try:
            _batch_collect_papers_impl(page_limit, batch_id)
        except Exception as e:
            rprint(f"[red]Error in link collection step: {e}[/red]")
            raise typer.Exit(1)
    else:
        rprint(f"[yellow]Skipping link collection step[/yellow]")
    
    # Step 2: Clean links
    if not skip_clean_links:
        rprint(f"\n[bold yellow]Step 2/4: Cleaning links with LLM...[/bold yellow]")
        try:
            _batch_clean_links_impl(batch_id, force)
        except Exception as e:
            rprint(f"[red]Error in link cleaning step: {e}[/red]")
            raise typer.Exit(1)
    else:
        rprint(f"[yellow]Skipping link cleaning step[/yellow]")
    
    # Step 3: Scrape articles from archive
    if not skip_scrape:
        rprint(f"\n[bold yellow]Step 3/4: Scraping articles from archive...[/bold yellow]")
        try:
            _batch_archive_scrape_articles_impl(batch_id, force, article_limit)
        except Exception as e:
            rprint(f"[red]Error in article scraping step: {e}[/red]")
            raise typer.Exit(1)
    else:
        rprint(f"[yellow]Skipping article scraping step[/yellow]")
    
    # Step 4: Clean articles
    if not skip_clean_articles:
        rprint(f"\n[bold yellow]Step 4/4: Cleaning articles with LLM...[/bold yellow]")
        try:
            _batch_clean_articles_impl(batch_id, force)
        except Exception as e:
            rprint(f"[red]Error in article cleaning step: {e}[/red]")
            raise typer.Exit(1)
    else:
        rprint(f"[yellow]Skipping article cleaning step[/yellow]")
    
    rprint(f"\n[bold green]✓ Batch pipeline complete for batch_id: {batch_id}[/bold green]")

if __name__ == "__main__":
    app()