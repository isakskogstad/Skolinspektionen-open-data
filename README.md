# Skolinspektionen DATA

Open data from Skolinspektionen (Swedish Schools Inspectorate) via MCP.

## Overview

This project provides structured access to public data from [Skolinspektionen](https://www.skolinspektionen.se), the Swedish Schools Inspectorate. It includes:

- **Intelligent Search**: BM25 relevance ranking + fuzzy matching for typo tolerance
- **Publication Index**: A searchable index of reports, decisions, and publications
- **On-demand Content Fetching**: Fetch full content as Markdown with caching
- **Statistics Files**: Direct access to Excel and PDF statistics
- **MCP Server**: AI-native integration via Model Context Protocol
- **Smart Caching**: Two-tier memory + disk cache for fast repeated queries
- **Rate Limiting**: Respectful scraping with token bucket algorithm
- **Delta Updates**: Only fetch new/changed content since last update

## Installation

```bash
pip install skolinspektionen-data
```

### Optional Dependencies

```bash
# With Camoufox browser for JavaScript-heavy pages
pip install "skolinspektionen-data[scraper]"

# With development tools
pip install "skolinspektionen-data[dev]"

# All dependencies
pip install "skolinspektionen-data[all]"
```

Or install from source:

```bash
git clone https://github.com/civictechsweden/skolinspektionen-data
cd skolinspektionen-data
pip install -e ".[dev]"
```

## Usage

### CLI Tools

**Refresh the publication index:**

```bash
si-scrape
```

**Run the MCP server:**

```bash
si-mcp
```

### MCP Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "skolinspektionen": {
      "command": "si-mcp"
    }
  }
}
```

Or with uvx (no installation required):

```json
{
  "mcpServers": {
    "skolinspektionen": {
      "command": "uvx",
      "args": ["skolinspektionen-data"]
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_publications` | Search publications with BM25 ranking and fuzzy matching |
| `search_press_releases` | Search press releases by query and year |
| `get_publication_content` | Fetch full publication content as Markdown |
| `get_publication_metadata` | Get publication metadata (faster than full content) |
| `list_publication_types` | List all publication types |
| `list_themes` | List all inspection themes |
| `get_statistics_files` | Get available statistics files (Excel, PDF) |
| `refresh_index` | Refresh the publication index |
| `get_cache_stats` | Get cache statistics for monitoring |
| `health_check` | Check service health and data freshness |

### MCP Resources

| Resource | Description |
|----------|-------------|
| `skolinspektionen://publication-types` | All publication types as JSON |
| `skolinspektionen://themes` | All inspection themes as JSON |
| `skolinspektionen://recent` | 20 most recent publications |

### MCP Prompts

| Prompt | Description |
|--------|-------------|
| `summarize_publication` | Summarize a publication from URL |
| `find_school_decisions` | Find inspection decisions for a school |
| `compare_inspections` | Compare inspection results by theme |

## Data Sources

- **Publications**: Quality reviews, government reports, statistics reports, annual reports
- **Press Releases**: News and announcements
- **Statistics**: Excel files with inspection data by category and year
- **Decisions**: School inspection results

## Project Architecture

```
src/
├── config.py           # Configuration with pydantic-settings
├── mcp/
│   └── server.py       # MCP server with tools, resources, prompts
├── search/
│   └── ranker.py       # BM25 + fuzzy search ranking
└── services/
    ├── browser.py      # Camoufox browser for JS pages
    ├── cache.py        # Two-tier LRU + disk cache
    ├── delta.py        # Incremental update calculation
    ├── models.py       # Pydantic data models
    ├── parser.py       # HTML to Markdown conversion
    ├── rate_limiter.py # Token bucket rate limiting
    ├── retry.py        # Exponential backoff + circuit breaker
    └── scraper.py      # Publication scraper
```

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `SI_BASE_URL` | `https://www.skolinspektionen.se` | Base URL |
| `SI_DATA_DIR` | `~/.skolinspektionen-data` | Data directory |
| `SI_CACHE_TTL_HOURS` | `24` | Cache TTL in hours |
| `SI_RATE_LIMIT` | `2.0` | Requests per second |
| `SI_LOG_LEVEL` | `INFO` | Logging level |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Lint code
ruff check src/

# Type check
mypy src/
```

### Test Coverage

The project maintains 80%+ test coverage with comprehensive tests for:
- All MCP tools and resources
- Search ranking algorithms
- Caching layers
- Rate limiting and retry logic
- HTML parsing and content extraction

## License

AGPL-3.0 - See [LICENSE](LICENSE) for details.

## Contributing

This is a Civic Tech Sweden project. Contributions welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure tests pass (`pytest`)
5. Submit a pull request

## Related Projects

- [g0vse](https://github.com/civictechsweden/g0vse) - Similar project for regeringen.se
- [jplusplus/skolstatistik](https://github.com/jplusplus/skolstatistik) - School statistics data
- [SCB MCP](https://github.com/civictechsweden/scb-mcp) - Statistics Sweden via MCP
- [Kolada MCP](https://github.com/civictechsweden/kolada-mcp) - Swedish municipality data via MCP
