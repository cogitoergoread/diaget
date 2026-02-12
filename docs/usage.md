# `dget` Usage Guide

`dget` is a command-line tool that loads JavaScript-rendered pages with Selenium and saves either rendered HTML or extracted visible text.

Use this guide to install, run, and troubleshoot the tool.

## What `dget` does

At a high level, `dget`:

1. Starts headless Chrome.
2. Opens the target URL.
3. Waits for page render completion and reader/iframe content.
4. Collects multiple candidate snapshots.
5. Selects the best snapshot and removes common page-number artifacts.
6. Saves content as HTML or text.

## Prerequisites

- Python `>= 3.14`
- Chrome/Chromium available to Selenium
- Network access to the target page

Python dependency:
- `selenium>=4.40.0`

If driver auto-resolution is blocked in your environment, install a compatible ChromeDriver and ensure it is available on `PATH`.

## Installation

From project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or install dependency directly:

```bash
pip install selenium
```

## Command syntax

```bash
dget <url> -o <output_file> [options]
```

### Required

- `<url>`: target URL to fetch
- `-o, --output`: destination file path

### Optional

- `--timeout <seconds>` (default: `20`)
- `--user-agent <string>`
- `--min-text-chars <n>` (default: `300`)
- `--format <html|text>` (default: `html`)

## Output behavior

- `--format html`: saves selected rendered HTML snapshot.
- `--format text`: saves cleaned visible text from rendered content.
- Parent output directories are created automatically.
- Exit code `0` indicates success, `1` indicates failure.

## Examples

### 1) Save rendered HTML

```bash
dget "https://reader.dia.hu/document/Krasznahorkai_Laszlo-Az_ellenallas_melankoliaja-1083" -o out/book.html
```

### 2) Save extracted text

```bash
dget "https://reader.dia.hu/document/Krasznahorkai_Laszlo-Az_ellenallas_melankoliaja-1083" -o out/book.txt --format text
```

### 3) Slower site, longer wait

```bash
dget "https://example.com/reader" -o out/page.html --timeout 45
```

### 4) Stricter text threshold

```bash
dget "https://example.com/reader" -o out/page.txt --format text --min-text-chars 1200
```

### 5) Custom user agent

```bash
dget "https://example.com/reader" -o out/page.html --user-agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
```

### 6) Save logs to file

```bash
dget "https://example.com/reader" -o out/page.html 2>&1 | tee out/dget-run.log
```

## Troubleshooting

### `Failed to start Chrome WebDriver`

Possible causes:
- Chrome is not installed
- Driver resolution/download is blocked
- Runtime sandbox restrictions

Try:
1. Verify Chrome is installed and runnable.
2. Ensure internet access for Selenium Manager.
3. Provide a compatible ChromeDriver on `PATH` in restricted environments.

### Output seems incomplete

- Increase `--timeout` (`45` or `60`).
- Increase `--min-text-chars`.
- Retry when source site load is lower.

### Built-in help

```bash
dget --help
```