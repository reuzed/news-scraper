# Setup

- Download the packages with `uv`, just `uv sync` or `uv run ...` something.
- You may need to set up a chromedriver for the `selenium` package to be able to run.
- You need to set an OpenAI API key in `.env` (see `.env.example`) for LLM features.

# CLI

To learn how to use the CLI run:

```bash
uv run cli.py --help
uv run cli.py run-batch --help
```

To run a scraping job call:

```bash
# For testing (takes 20 mins and requires you to fill CAPTCHA halfway through)
uv run cli.py run-batch --page-limit 2 --batch-id test --article-limit 2
# Takes longer...
uv run cli.py run-batch --page-limit 15
```

# Pipeline will look like

1. Find list of article links
2. Clean the list of links with LLM
3. Scrape articles text
4. Clean article text with LLM
