#!/usr/bin/env python3
"""CLI tool to fetch rendered HTML using Selenium."""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


LOG = logging.getLogger("dget")


@dataclass(frozen=True)
class FetchConfig:
    url: str
    output_file: Path
    timeout_seconds: int = 20
    user_agent: Optional[str] = None
    min_text_chars: int = 300
    output_format: str = "html"


@dataclass(frozen=True)
class DocumentSnapshot:
    html: str
    text: str
    context: str


class HtmlFetcher:
    """Fetch rendered HTML using a headless Chrome browser."""

    def __init__(
        self,
        timeout_seconds: int = 20,
        user_agent: Optional[str] = None,
        min_text_chars: int = 300,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._min_text_chars = min_text_chars

    def fetch(self, url: str) -> DocumentSnapshot:
        options = self._build_options()
        try:
            driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:
            raise RuntimeError("Failed to start Chrome WebDriver") from exc

        try:
            driver.get(url)
            WebDriverWait(driver, self._timeout_seconds).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            self._wait_for_epub_runtime(driver)
            self._activate_book_content_view(driver)
            self._wait_for_reader_iframe_content(driver)
            self._wait_for_rendered_text(driver)
            component_snapshot = self._snapshot_from_component_endpoints(driver)

            top_level = self._snapshot_current_document(driver, "top")
            frame_snapshots = self._collect_frame_snapshots(driver)
            candidates = [top_level, *frame_snapshots]
            if component_snapshot:
                candidates.append(component_snapshot)
            best_snapshot = max(
                candidates,
                key=self._snapshot_score,
            )
            best_snapshot = self._without_page_number_spans(best_snapshot)
            LOG.info(
                "Selected rendered context '%s' with %d text chars",
                best_snapshot.context,
                len(best_snapshot.text),
            )
            return best_snapshot
        finally:
            driver.quit()

    def _wait_for_rendered_text(self, driver: webdriver.Chrome) -> None:
        def max_text_length(current_driver: webdriver.Chrome) -> int:
            return int(
                current_driver.execute_script(
                    """
                    const textLengthForDoc = (doc) => {
                        if (!doc || !doc.body) return 0;
                        const selectors = [
                            '#reader .monelem_component',
                            '#reader .monelem_page',
                            '#reader',
                            '.monelem_page',
                            '.monelem_sheaf',
                            '.monelem_component',
                            'article',
                            'main',
                            '#content',
                            '.content',
                            '.chapter',
                            '.text',
                            'body'
                        ];
                        let best = 0;
                        for (const selector of selectors) {
                            const nodes = doc.querySelectorAll(selector);
                            for (const node of nodes) {
                                const len = (node.innerText || '').trim().length;
                                if (len > best) best = len;
                            }
                        }
                        return best;
                    };

                    const maxLen = (doc) => {
                        if (!doc) return 0;
                        let best = textLengthForDoc(doc);
                        const frames = doc.querySelectorAll('iframe');
                        for (const frame of frames) {
                            try {
                                const childDoc = frame.contentDocument;
                                if (!childDoc) continue;
                                const childLen = maxLen(childDoc);
                                if (childLen > best) best = childLen;
                            } catch (_err) {
                            }
                        }
                        return best;
                    };
                    return maxLen(document);
                    """
                )
            )

        try:
            WebDriverWait(driver, self._timeout_seconds).until(
                lambda current_driver: max_text_length(current_driver) >= self._min_text_chars
            )
        except Exception:
            current_max = max_text_length(driver)
            LOG.warning(
                "Timed out waiting for %d rendered text chars (max observed: %d)",
                self._min_text_chars,
                current_max,
            )

    def _wait_for_epub_runtime(self, driver: webdriver.Chrome) -> None:
        try:
            WebDriverWait(driver, self._timeout_seconds).until(
                lambda current_driver: bool(
                    current_driver.execute_script(
                        """
                        const hasRuntime = typeof window.EpubReader !== 'undefined';
                        const hasReaderContainer = !!document.querySelector('#reader');
                        const hasReaderFrame = !!document.querySelector('#reader iframe.monelem_component');
                        return hasRuntime && hasReaderContainer && hasReaderFrame;
                        """
                    )
                )
            )
        except Exception:
            LOG.warning("Timed out waiting for EpubReader runtime initialization")

    def _wait_for_reader_iframe_content(self, driver: webdriver.Chrome) -> None:
        def reader_iframe_text_length(current_driver: webdriver.Chrome) -> int:
            return int(
                current_driver.execute_script(
                    """
                    const readers = Array.from(document.querySelectorAll('#reader iframe.monelem_component'));
                    let best = 0;
                    for (const iframe of readers) {
                        try {
                            const doc = iframe.contentDocument;
                            if (!doc || !doc.body) continue;
                            const text = (doc.body.innerText || '').trim();
                            if (text.length > best) best = text.length;
                        } catch (_err) {
                        }
                    }
                    return best;
                    """
                )
            )

        try:
            WebDriverWait(driver, self._timeout_seconds).until(
                lambda current_driver: reader_iframe_text_length(current_driver) >= self._min_text_chars
            )
        except Exception:
            observed = reader_iframe_text_length(driver)
            LOG.warning(
                "Timed out waiting for reader iframe text (min %d, observed %d)",
                self._min_text_chars,
                observed,
            )

    def _snapshot_current_document(self, driver: webdriver.Chrome, context: str) -> DocumentSnapshot:
        html = str(
            driver.execute_script(
                """
                const clonedDoc = document.cloneNode(true);
                clonedDoc.querySelectorAll('.oldaltores').forEach((node) => node.remove());
                clonedDoc.querySelectorAll('a[name^="DIAPage"]').forEach((node) => node.remove());
                return clonedDoc.documentElement.outerHTML || '';
                """
            )
        )
        text = self._best_text_from_html(html)
        return DocumentSnapshot(html=html, text=text.strip(), context=context)

    def _snapshot_score(self, snapshot: DocumentSnapshot) -> tuple[int, int]:
        lowered = snapshot.text.lower()
        metadata_keywords = (
            "tartalomjegyzék",
            "szerző további művei",
            "metaadatok",
            "szöveg keresése",
        )
        metadata_penalty = 1 if all(keyword in lowered for keyword in metadata_keywords[:2]) else 0
        iframe_bonus = 1 if "iframe" in snapshot.context else 0
        component_bonus = 2 if snapshot.context.startswith("component") else 0
        prose_bonus = 1 if "bevezetés" in lowered or "rendkívüli állapotok" in lowered else 0
        score = len(snapshot.text) - (2000 if metadata_penalty else 0)
        return (component_bonus, prose_bonus, iframe_bonus, score)

    def _snapshot_from_component_endpoints(self, driver: webdriver.Chrome) -> Optional[DocumentSnapshot]:
        chapter_paths = self._chapter_component_paths(driver)
        if not chapter_paths:
            return None

        selected_paths: list[str] = []
        for path in chapter_paths:
            lowered = path.lower()
            if "szerzoseg" in lowered:
                continue
            selected_paths.append(path)
            if len(selected_paths) >= 4:
                break

        if not selected_paths:
            return None

        parts: list[dict[str, str]] = list(
            driver.execute_async_script(
                """
                const paths = arguments[0];
                const done = arguments[arguments.length - 1];

                Promise.all(paths.map(async (path) => {
                    try {
                        const response = await fetch(path, { credentials: 'include' });
                        if (!response.ok) {
                            return { path, html: '', text: '' };
                        }
                        const markup = await response.text();
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(markup, 'text/html');
                        const text = (doc.body && doc.body.innerText) ? doc.body.innerText.trim() : '';
                        const html = doc.documentElement ? doc.documentElement.outerHTML : markup;
                        return { path, html, text };
                    } catch (_error) {
                        return { path, html: '', text: '' };
                    }
                })).then(done);
                """,
                selected_paths,
            )
        )

        valid_parts = [part for part in parts if part.get("text", "").strip()]
        if not valid_parts:
            return None

        combined_html = "\n".join(part["html"] for part in valid_parts)
        combined_text = self._best_text_from_html(combined_html)
        LOG.info(
            "Fetched %d chapter component(s) via /rest endpoint (%d text chars)",
            len(valid_parts),
            len(combined_text),
        )
        return DocumentSnapshot(
            html=combined_html,
            text=combined_text,
            context="component-api",
        )

    def _chapter_component_paths(self, driver: webdriver.Chrome) -> list[str]:
        paths: list[str] = list(
            driver.execute_script(
                """
                const nodes = Array.from(document.querySelectorAll('#toc-view li[data-chapter]'));
                const values = [];
                for (const node of nodes) {
                    const path = node.getAttribute('data-chapter') || '';
                    if (path) values.push(path);
                }
                return values;
                """
            )
        )
        return paths

    def _without_page_number_spans(self, snapshot: DocumentSnapshot) -> DocumentSnapshot:
        cleaned_html = re.sub(
            r"<([a-z0-9]+)\b[^>]*\bclass\s*=\s*['\"][^'\"]*\boldaltores\b[^'\"]*['\"][^>]*>.*?</\1>",
            "",
            snapshot.html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned_html = re.sub(
            r"<a\b[^>]*\bname\s*=\s*['\"]DIAPage[^'\"]*['\"][^>]*>\s*</a>",
            "",
            cleaned_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned_text = self._best_text_from_html(cleaned_html)
        if not cleaned_text.strip():
            cleaned_text = re.sub(r"\b\d+\b", "", snapshot.text)
            cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
            cleaned_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned_text)
        return DocumentSnapshot(
            html=cleaned_html,
            text=cleaned_text.strip(),
            context=snapshot.context,
        )

    def _best_text_from_html(self, html: str) -> str:
        return self._extract_text_with_fallback(html)

    def _extract_text_with_fallback(self, html: str) -> str:
        body_match = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.IGNORECASE | re.DOTALL)
        source = body_match.group(1) if body_match else html
        source = re.sub(r"<script\b[^>]*>.*?</script>", "", source, flags=re.IGNORECASE | re.DOTALL)
        source = re.sub(r"<style\b[^>]*>.*?</style>", "", source, flags=re.IGNORECASE | re.DOTALL)
        source = re.sub(r"<br\s*/?>", "\n", source, flags=re.IGNORECASE)
        source = re.sub(r"</(p|div|h1|h2|h3|h4|h5|h6|li|tr|section|article|header|footer)>", "\n", source, flags=re.IGNORECASE)
        source = re.sub(r"<[^>]+>", "", source)
        source = re.sub(r"&nbsp;", " ", source, flags=re.IGNORECASE)
        source = re.sub(r"\s+\n", "\n", source)
        source = re.sub(r"\n\s+", "\n", source)
        source = re.sub(r"(?m)^\s*\d{1,4}\s*$\n?", "", source)
        source = re.sub(r"\n{3,}", "\n\n", source)
        source = re.sub(r"[ \t]{2,}", " ", source)
        return source.strip()

    def _activate_book_content_view(self, driver: webdriver.Chrome) -> None:
        activated = bool(
            driver.execute_script(
                """
                const click = (node) => {
                    if (!node) return false;
                    node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                    return true;
                };

                click(document.querySelector('#toc-nav'));

                const chapterItems = Array.from(document.querySelectorAll('#toc-view li[data-chapter]'));
                if (chapterItems.length === 0) return false;

                const score = (item) => {
                    const chapter = (item.getAttribute('data-chapter') || '').toLowerCase();
                    let value = 0;
                    if (chapter.includes('szerzoseg')) value -= 100;
                    if (chapter.includes('krasznahorkai00014')) value += 40;
                    if (chapter.includes('-00020')) value += 30;
                    if (item.classList.contains('single-chapter')) value += 10;
                    const text = (item.innerText || '').toLowerCase();
                    if (text.includes('rendkívüli állapotok') || text.includes('rendkivuli allapotok')) value += 20;
                    if (text.includes('bevezetés') || text.includes('bevezetes')) value += 10;
                    return value;
                };

                let best = chapterItems[0];
                let bestScore = score(best);
                for (const item of chapterItems) {
                    const currentScore = score(item);
                    if (currentScore > bestScore) {
                        bestScore = currentScore;
                        best = item;
                    }
                }

                const clickable = best.querySelector('span') || best;
                click(best);
                click(clickable);
                return true;
                """
            )
        )
        if activated:
            LOG.info("Activated book chapter from table of contents")

    def _collect_frame_snapshots(
        self,
        driver: webdriver.Chrome,
        context: str = "top",
        depth: int = 0,
        max_depth: int = 4,
    ) -> list[DocumentSnapshot]:
        if depth >= max_depth:
            return []

        snapshots: list[DocumentSnapshot] = []
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for index, frame in enumerate(frames):
            frame_context = f"{context}/iframe[{index}]"
            try:
                driver.switch_to.frame(frame)
                snapshots.append(self._snapshot_current_document(driver, frame_context))
                snapshots.extend(
                    self._collect_frame_snapshots(
                        driver,
                        context=frame_context,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                )
            except Exception as exc:
                LOG.debug("Failed to inspect frame %s: %s", frame_context, exc)
            finally:
                try:
                    driver.switch_to.parent_frame()
                except Exception:
                    driver.switch_to.default_content()

        return snapshots

    def _build_options(self) -> Options:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if self._user_agent:
            options.add_argument(f"--user-agent={self._user_agent}")
        return options


class HtmlSaver:
    """Persist HTML to disk."""

    def save(self, html: str, output_file: Path) -> None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html, encoding="utf-8")


def parse_args(argv: Optional[list[str]] = None) -> FetchConfig:
    parser = argparse.ArgumentParser(
        prog="dget",
        description="Fetch rendered HTML from a JavaScript-driven page.",
    )
    parser.add_argument("url", help="Target URL to fetch")
    parser.add_argument("-o", "--output", required=True, help="Output HTML file")
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Seconds to wait for the page to finish rendering",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Custom user agent string",
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=300,
        help="Minimum rendered text characters to wait for before capturing",
    )
    parser.add_argument(
        "--format",
        choices=["html", "text"],
        default="html",
        help="Output format: rendered HTML or visible rendered text",
    )
    args = parser.parse_args(argv)

    return FetchConfig(
        url=args.url,
        output_file=Path(args.output),
        timeout_seconds=args.timeout,
        user_agent=args.user_agent,
        min_text_chars=args.min_text_chars,
        output_format=args.format,
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def run(config: FetchConfig) -> None:
    fetcher = HtmlFetcher(
        timeout_seconds=config.timeout_seconds,
        user_agent=config.user_agent,
        min_text_chars=config.min_text_chars,
    )
    saver = HtmlSaver()

    LOG.info("Fetching HTML from %s", config.url)
    snapshot = fetcher.fetch(config.url)
    content = snapshot.html if config.output_format == "html" else snapshot.text

    LOG.info("Saving %s to %s", config.output_format.upper(), config.output_file)
    saver.save(content, config.output_file)
    LOG.info("Done")


def main(argv: Optional[list[str]] = None) -> int:
    configure_logging()
    try:
        config = parse_args(argv)
        run(config)
    except Exception as exc:  # pragma: no cover - CLI surface
        LOG.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
