"""Small dependency-free article text cleaner for bounded HTML responses."""

from html.parser import HTMLParser
from dataclasses import dataclass
import re


SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside", "form", "noscript"})
TEXT_TAGS = frozenset({"h1", "h2", "h3", "p", "li", "blockquote"})


@dataclass(frozen=True)
class ArticleLink:
    href: str
    label: str
    context: str


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._tag: str | None = None
        self._current: list[str] = []
        self.paragraphs: list[str] = []
        self.links: list[ArticleLink] = []
        self._pending_links: list[tuple[str, str]] = []
        self._active_link: tuple[str, int] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif not self._skip_depth and tag in TEXT_TAGS and self._tag is None:
            self._tag = tag
            self._current = []
            self._pending_links = []
        elif not self._skip_depth and tag == "a" and self._tag is not None:
            href = dict(attrs).get("href")
            if href:
                self._active_link = (href, len(self._current))

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag == "a" and self._active_link is not None:
            href, start = self._active_link
            label = re.sub(r"\s+", " ", " ".join(self._current[start:])).strip()
            self._pending_links.append((href, label))
            self._active_link = None
        elif not self._skip_depth and tag == self._tag:
            paragraph = re.sub(r"\s+", " ", " ".join(self._current)).strip()
            if paragraph:
                self.paragraphs.append(paragraph)
                self.links.extend(ArticleLink(href, label, paragraph)
                                  for href, label in self._pending_links)
            self._tag = None
            self._current = []
            self._pending_links = []
            self._active_link = None

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and self._tag is not None:
            self._current.append(data)


def extract_html_text(html: str) -> str:
    return parse_html(html)[0]


def parse_html(html: str) -> tuple[str, tuple[ArticleLink, ...]]:
    parser = _ArticleParser()
    parser.feed(html)
    return "\n\n".join(parser.paragraphs), tuple(parser.links)
