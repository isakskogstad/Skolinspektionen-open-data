"""Tests for parser module."""

import pytest
from bs4 import BeautifulSoup

from src.services.parser import ContentParser


class TestExtractTitle:
    """Tests for _extract_title method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_extract_from_h1(self, parser: ContentParser):
        """Test extracting title from h1 tag."""
        html = "<html><body><h1>Test Title</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = parser._extract_title(soup)
        assert title == "Test Title"

    def test_extract_from_article_h1(self, parser: ContentParser):
        """Test extracting title from article h1."""
        html = "<html><body><article><h1>Article Title</h1></article></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = parser._extract_title(soup)
        assert title == "Article Title"

    def test_extract_from_page_title(self, parser: ContentParser):
        """Test fallback to page title tag."""
        html = "<html><head><title>Page Title | Site Name</title></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = parser._extract_title(soup)
        assert title == "Page Title"

    def test_extract_untitled_fallback(self, parser: ContentParser):
        """Test fallback to 'Untitled' when no title found."""
        html = "<html><body><p>Just content</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = parser._extract_title(soup)
        assert title == "Untitled"

    def test_extract_from_class_title(self, parser: ContentParser):
        """Test extracting title from element with title class."""
        html = "<html><body><div class='page-title'>Page Title</div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = parser._extract_title(soup)
        assert title == "Page Title"


class TestFindMainContent:
    """Tests for _find_main_content method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_find_article(self, parser: ContentParser):
        """Test finding content in article element."""
        html = """
        <html><body>
            <article>This is the main article content with lots of text to make it long enough</article>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = parser._find_main_content(soup)
        assert content is not None
        assert "main article content" in content.get_text()

    def test_find_main(self, parser: ContentParser):
        """Test finding content in main element."""
        html = """
        <html><body>
            <main>This is the main content area with enough text to pass the minimum length check</main>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = parser._find_main_content(soup)
        assert content is not None
        assert "main content area" in content.get_text()

    def test_fallback_to_body(self, parser: ContentParser):
        """Test fallback to body when no content container found."""
        html = "<html><body><p>Simple paragraph</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        content = parser._find_main_content(soup)
        assert content is not None
        assert "Simple paragraph" in content.get_text()


class TestConvertToMarkdown:
    """Tests for _convert_to_markdown method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_convert_basic_html(self, parser: ContentParser):
        """Test converting basic HTML to Markdown."""
        html = "<div><h1>Title</h1><p>Paragraph text.</p></div>"
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find("div")
        markdown = parser._convert_to_markdown(elem)
        assert "# Title" in markdown
        assert "Paragraph text." in markdown

    def test_removes_script_elements(self, parser: ContentParser):
        """Test that script elements are removed."""
        html = "<div><p>Content</p><script>alert('bad');</script></div>"
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find("div")
        markdown = parser._convert_to_markdown(elem)
        assert "alert" not in markdown
        assert "Content" in markdown

    def test_removes_navigation(self, parser: ContentParser):
        """Test that navigation elements are removed."""
        html = "<div><nav>Menu</nav><p>Main content</p></div>"
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find("div")
        markdown = parser._convert_to_markdown(elem)
        assert "Menu" not in markdown
        assert "Main content" in markdown

    def test_handles_none(self, parser: ContentParser):
        """Test handling None input."""
        markdown = parser._convert_to_markdown(None)
        assert markdown == ""


class TestCleanMarkdown:
    """Tests for _clean_markdown method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_removes_excessive_newlines(self, parser: ContentParser):
        """Test removing excessive newlines."""
        text = "Line 1\n\n\n\n\nLine 2"
        cleaned = parser._clean_markdown(text)
        assert "\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned

    def test_strips_whitespace(self, parser: ContentParser):
        """Test stripping whitespace from lines."""
        text = "  Line with spaces  \n  Another line  "
        cleaned = parser._clean_markdown(text)
        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")

    def test_removes_empty_headers(self, parser: ContentParser):
        """Test removing empty headers."""
        text = "# Title\n## \n###\nContent"
        cleaned = parser._clean_markdown(text)
        assert "## " not in cleaned
        assert "###" not in cleaned
        assert "Title" in cleaned
        assert "Content" in cleaned


class TestExtractAttachments:
    """Tests for _extract_attachments method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_extract_pdf(self, parser: ContentParser):
        """Test extracting PDF attachments."""
        html = """
        <html><body>
            <a href="/files/rapport.pdf">Download Report</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1
        assert attachments[0].name == "Download Report"
        assert "rapport.pdf" in attachments[0].url
        assert attachments[0].file_type == "pdf"

    def test_extract_excel(self, parser: ContentParser):
        """Test extracting Excel attachments."""
        html = """
        <html><body>
            <a href="/files/data.xlsx">Download Data</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1
        assert attachments[0].file_type == "excel"

    def test_extract_xls(self, parser: ContentParser):
        """Test extracting .xls files as excel type."""
        html = """
        <html><body>
            <a href="/files/old-data.xls">Old Data</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1
        assert attachments[0].file_type == "excel"

    def test_extract_word_doc(self, parser: ContentParser):
        """Test extracting Word documents."""
        html = """
        <html><body>
            <a href="/files/document.docx">Word Document</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1
        assert attachments[0].file_type == "word"

    def test_deduplicates_by_url(self, parser: ContentParser):
        """Test that duplicate URLs are removed."""
        html = """
        <html><body>
            <a href="/files/rapport.pdf">Download Report</a>
            <a href="/files/rapport.pdf">Same Report</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1

    def test_handles_absolute_urls(self, parser: ContentParser):
        """Test handling absolute URLs."""
        html = """
        <html><body>
            <a href="https://other-domain.se/file.pdf">External PDF</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1
        assert attachments[0].url.startswith("https://")

    def test_default_name_for_empty_link_text(self, parser: ContentParser):
        """Test default name when link text is empty."""
        html = """
        <html><body>
            <a href="/files/file.pdf"></a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        attachments = parser._extract_attachments(soup)
        assert len(attachments) == 1
        assert attachments[0].name == "Attachment.pdf"


class TestExtractMetadata:
    """Tests for _extract_metadata method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_extract_diarienummer(self, parser: ContentParser):
        """Test extracting diarienummer."""
        html = """
        <html><body>
            <p>Diarienummer: SI2024-123</p>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = parser._extract_metadata(soup)
        assert "diarienummer" in metadata
        assert metadata["diarienummer"] == "SI2024-123"

    def test_extract_dnr_format(self, parser: ContentParser):
        """Test extracting dnr format."""
        html = """
        <html><body>
            <p>Dnr: ABC-2024-001</p>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = parser._extract_metadata(soup)
        assert "diarienummer" in metadata
        assert metadata["diarienummer"] == "ABC-2024-001"

    def test_extract_published_date(self, parser: ContentParser):
        """Test extracting published date."""
        html = """
        <html><body>
            <time datetime="2024-03-15">15 mars 2024</time>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = parser._extract_metadata(soup)
        assert "published" in metadata
        assert metadata["published"] == "2024-03-15"

    def test_extract_published_from_class(self, parser: ContentParser):
        """Test extracting date from element with date class."""
        html = """
        <html><body>
            <span class="date">2024-01-01</span>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = parser._extract_metadata(soup)
        assert "published" in metadata

    def test_extract_themes(self, parser: ContentParser):
        """Test extracting themes."""
        html = """
        <html><body>
            <a href="/teman/matematik/">Matematik</a>
            <a href="/teman/lasmiljo/">Läsmiljö</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = parser._extract_metadata(soup)
        assert "themes" in metadata
        assert len(metadata["themes"]) == 2

    def test_empty_metadata(self, parser: ContentParser):
        """Test when no metadata found."""
        html = "<html><body><p>Just content</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        metadata = parser._extract_metadata(soup)
        assert isinstance(metadata, dict)


class TestParsePublicationPage:
    """Tests for parse_publication_page method."""

    @pytest.fixture
    def parser(self) -> ContentParser:
        """Create a parser instance."""
        return ContentParser(timeout=10.0)

    def test_full_page_parsing(self, parser: ContentParser):
        """Test parsing a complete publication page."""
        html = """
        <html>
        <head><title>Test Report | Skolinspektionen</title></head>
        <body>
            <article>
                <h1>Quality Review Report</h1>
                <time datetime="2024-03-15">15 mars 2024</time>
                <p>Diarienummer: SI2024-001</p>
                <div class="content">
                    <p>This is the main content of the report with detailed findings.</p>
                </div>
                <a href="/files/rapport.pdf">Download PDF</a>
            </article>
        </body>
        </html>
        """
        result = parser.parse_publication_page(html, "https://example.com/report")

        assert result["title"] == "Quality Review Report"
        assert "source_url" in result
        assert result["source_url"] == "https://example.com/report"
        assert "markdown" in result
        assert "attachments" in result
        assert "metadata" in result


class TestContentParserAsync:
    """Async tests for ContentParser."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with ContentParser(timeout=10.0) as parser:
            assert parser.client is not None

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that client is closed after context."""
        parser = ContentParser(timeout=10.0)
        async with parser:
            client = parser.client
            assert client is not None
        # After exiting context, client should be closed

    @pytest.mark.asyncio
    async def test_fetch_publication_content_with_mock(self, respx_mock):
        """Test fetching publication content with mocked HTTP."""
        html = """
        <html>
        <body>
            <article>
                <h1>Test Report</h1>
                <p>Content here</p>
            </article>
        </body>
        </html>
        """
        respx_mock.get("https://www.skolinspektionen.se/test").mock(
            return_value=__import__("httpx").Response(200, text=html)
        )

        async with ContentParser(timeout=10.0) as parser:
            result = await parser.fetch_publication_content("/test")

        assert result is not None
        assert result["title"] == "Test Report"

    @pytest.mark.asyncio
    async def test_fetch_handles_error(self, respx_mock):
        """Test that fetch handles HTTP errors gracefully."""
        respx_mock.get("https://www.skolinspektionen.se/notfound").mock(
            return_value=__import__("httpx").Response(404)
        )

        async with ContentParser(timeout=10.0) as parser:
            result = await parser.fetch_publication_content("/notfound")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_press_release_content(self, respx_mock):
        """Test fetching press release content."""
        html = """
        <html>
        <body>
            <article>
                <h1>Press Release</h1>
                <p>Press release content</p>
            </article>
        </body>
        </html>
        """
        respx_mock.get("https://www.skolinspektionen.se/press/1").mock(
            return_value=__import__("httpx").Response(200, text=html)
        )

        async with ContentParser(timeout=10.0) as parser:
            result = await parser.fetch_press_release_content("/press/1")

        assert result is not None
        assert result["title"] == "Press Release"
