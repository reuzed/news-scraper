# Setup

- Download the packages with `uv`, just `uv sync` or `uv run ...` something.
- You may need to set up a chromedriver for the `selenium` package to be able to run.
- You need to set an OpenAI API key in `.env` (see `.env.example`) for LLM features.

# CLI

# Pipeline will look like

1. Find list of article links
2. Clean the list of links with LLM
3. Scrape articles text
4. Clean article text with LLM
