#!/usr/bin/env python3
"""Generate a styled SVG card + collapsible markdown table for contributed repositories."""

import json
import os
import sys
import urllib.request

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
USERNAME = os.environ.get("USERNAME", "Br1an67")
LIMIT = int(os.environ.get("LIMIT", "0"))  # 0 = show all
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "10"))
SVG_OUTPUT = os.environ.get("SVG_OUTPUT", "metrics.plugin.contributions.svg")
README = os.environ.get("README", "README.md")

START_MARKER = "<!-- CONTRIBUTIONS:START -->"
END_MARKER = "<!-- CONTRIBUTIONS:END -->"

# onedark theme
THEME = {
    "bg": "#282c34",
    "title": "#e4e2e2",
    "text": "#adbac7",
    "link": "#58a6ff",
    "star": "#e3b341",
    "muted": "#7f848e",
    "border": "#3e4451",
    "stripe": "rgba(255,255,255,0.03)",
}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositoriesContributedTo(
      first: 100
      contributionTypes: [COMMIT, PULL_REQUEST, PULL_REQUEST_REVIEW]
      includeUserRepositories: false
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      nodes {
        nameWithOwner
        stargazerCount
        description
        primaryLanguage { name color }
      }
    }
  }
}
"""

STAR_ICON = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def query_github(token, login):
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contributions-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
        sys.exit(1)
    return data["data"]["user"]["repositoriesContributedTo"]["nodes"]


def format_stars(count):
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


def escape_xml(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def truncate(text, max_len=60):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def generate_svg(repos):
    """Generate an SVG card with onedark theme."""
    row_height = 50
    padding_top = 50
    padding_bottom = 15
    card_width = 830
    card_height = padding_top + len(repos) * row_height + padding_bottom

    L = []  # noqa: E741
    L.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{card_width}" height="{card_height}" viewBox="0 0 {card_width} {card_height}">')

    # Card background
    L.append(f'  <rect x="0.5" y="0.5" rx="4.5" width="{card_width - 1}" height="{card_height - 1}" fill="{THEME["bg"]}" stroke="{THEME["border"]}"/>')

    # Title
    L.append(f'  <text x="25" y="33" fill="{THEME["title"]}" font-family="{FONT}" font-size="15" font-weight="600">Top Contributed Repositories</text>')

    for i, repo in enumerate(repos):
        y = padding_top + i * row_height + 18
        name = repo["nameWithOwner"]
        stars = format_stars(repo["stargazerCount"])
        desc = truncate(escape_xml(repo.get("description") or ""), 75)
        lang = repo.get("primaryLanguage") or {}
        lang_name = lang.get("name", "")
        lang_color = lang.get("color", THEME["muted"])

        # Alternating row stripe
        if i % 2 == 1:
            L.append(f'  <rect x="1" y="{y - 15}" width="{card_width - 2}" height="{row_height}" fill="{THEME["stripe"]}"/>')

        # Repo name
        L.append(f'  <text x="25" y="{y}" fill="{THEME["link"]}" font-family="{FONT}" font-size="13.5" font-weight="600">{escape_xml(name)}</text>')

        # Star icon + count
        sx = 380
        L.append(f'  <g transform="translate({sx}, {y - 10})"><svg width="12" height="12" viewBox="0 0 16 16" fill="{THEME["star"]}"><path d="{STAR_ICON}"/></svg></g>')
        L.append(f'  <text x="{sx + 16}" y="{y}" fill="{THEME["star"]}" font-family="{FONT}" font-size="12">{stars}</text>')

        # Language
        if lang_name:
            lx = 450
            L.append(f'  <circle cx="{lx}" cy="{y - 4}" r="4.5" fill="{lang_color}"/>')
            L.append(f'  <text x="{lx + 9}" y="{y}" fill="{THEME["muted"]}" font-family="{FONT}" font-size="11">{escape_xml(lang_name)}</text>')

        # Description (second line)
        if desc:
            L.append(f'  <text x="25" y="{y + 16}" fill="{THEME["text"]}" font-family="{FONT}" font-size="11" opacity="0.65">{desc}</text>')

    L.append("</svg>")
    return "\n".join(L)


def generate_markdown_table(repos):
    """Generate a markdown table for remaining repos."""
    lines = []
    lines.append("| Repository | Stars | Language | Description |")
    lines.append("|:---|:---:|:---:|:---|")
    for repo in repos:
        name = repo["nameWithOwner"]
        stars = format_stars(repo["stargazerCount"])
        lang = (repo.get("primaryLanguage") or {}).get("name", "—")
        desc = truncate(repo.get("description") or "", 60)
        lines.append(f"| **{name}** | {stars} | {lang} | {desc} |")
    return "\n".join(lines)


def inject_into_readme(content_str, readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    start = content.find(START_MARKER)
    end = content.find(END_MARKER)
    if start == -1 or end == -1:
        print(f"Error: markers not found in {readme_path}", file=sys.stderr)
        sys.exit(1)
    new_content = content[: start + len(START_MARKER)] + "\n" + content_str + "\n" + content[end:]
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN or METRICS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching contributed repositories for {USERNAME}...")
    repos = query_github(GITHUB_TOKEN, USERNAME)
    print(f"Found {len(repos)} contributed repositories")

    repos = [r for r in repos if r["stargazerCount"] > 0]
    repos.sort(key=lambda r: r["stargazerCount"], reverse=True)
    if LIMIT > 0:
        repos = repos[:LIMIT]

    # Generate SVG card for top repos
    top_repos = repos[:PAGE_SIZE]
    svg = generate_svg(top_repos)
    with open(SVG_OUTPUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Generated {SVG_OUTPUT} with {len(top_repos)} repos")

    # Generate README section: SVG image + collapsible table for the rest
    readme_lines = []
    readme_lines.append('<p align="center">')
    readme_lines.append(f'  <img src="/{SVG_OUTPUT}" alt="Top Contributed Repos" />')
    readme_lines.append("</p>")

    remaining = repos[PAGE_SIZE:]
    if remaining:
        readme_lines.append("")
        readme_lines.append("<details>")
        readme_lines.append(f"<summary>Show more ({len(remaining)} repositories)</summary>")
        readme_lines.append("")
        readme_lines.append(generate_markdown_table(remaining))
        readme_lines.append("")
        readme_lines.append("</details>")

    inject_into_readme("\n".join(readme_lines), README)
    print(f"Updated {README}")


if __name__ == "__main__":
    main()
