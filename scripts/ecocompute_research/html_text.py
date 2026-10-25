"""Small dependency-free article text cleaner for bounded HTML responses."""

from html.parser import HTMLParser
import re


SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside", "form", "noscript"})
TEXT_TAGS = frozenset({"h1", "h2", "h3", "p", "li", "blockquote"})


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._tag: str | None = None
        self._current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif not self._skip_depth and tag in TEXT_TAGS and self._tag is None:
            self._tag = tag
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag == self._tag:
            paragraph = re.sub(r"\s+", " ", " ".join(self._current)).strip()
            if paragraph:
                self.paragraphs.append(paragraph)
            self._tag = None
            self._current = []

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and self._tag is not None:
            self._current.append(data)


def extract_html_text(html: str) -> str:
    parser = _ArticleParser()
    parser.feed(html)
    return "\n\n".join(parser.paragraphs)
