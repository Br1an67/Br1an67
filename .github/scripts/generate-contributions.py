#!/usr/bin/env python3
"""Generate an SVG card showing top contributed repositories (onedark theme)."""

import json
import math
import os
import sys
import urllib.request

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
USERNAME = os.environ.get("USERNAME", "Br1an67")
LIMIT = int(os.environ.get("LIMIT", "10"))
OUTPUT = os.environ.get("OUTPUT", "metrics.plugin.contributions.svg")

# onedark theme (matches github-readme-stats)
THEME = {
    "bg": "#282c34",
    "title": "#e4e2e2",
    "text": "#adbac7",
    "link": "#58a6ff",
    "star": "#e3b341",
    "icon": "#9e9e9e",
    "border": "#3e4451",
    "rank_s": "#e3b341",
    "rank_a": "#58a6ff",
    "rank_b": "#9e9e9e",
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


def query_github(token, login):
    """Query GitHub GraphQL API for contributed repositories."""
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contributions-card-generator",
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
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def truncate(text, max_len=70):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def generate_svg(repos, limit):
    """Generate an SVG card with onedark theme."""
    repos = repos[:limit]

    row_height = 50
    padding_top = 55
    padding_bottom = 20
    card_width = 830
    card_height = padding_top + len(repos) * row_height + padding_bottom

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{card_width}" height="{card_height}" viewBox="0 0 {card_width} {card_height}">')
    lines.append(f'  <rect x="0.5" y="0.5" rx="4.5" width="{card_width - 1}" height="{card_height - 1}" fill="{THEME["bg"]}" stroke="{THEME["border"]}"/>')

    # Title
    lines.append(f'  <text x="25" y="35" fill="{THEME["title"]}" font-family="\'Segoe UI\', Ubuntu, \'Helvetica Neue\', Sans-Serif" font-size="16" font-weight="600">Top Contributed Repositories</text>')

    # Star icon SVG path
    star_icon = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"

    for i, repo in enumerate(repos):
        y_base = padding_top + i * row_height + 20
        name = repo["nameWithOwner"]
        stars = repo["stargazerCount"]
        desc = truncate(escape_xml(repo.get("description") or ""), 80)
        lang = repo.get("primaryLanguage") or {}
        lang_name = lang.get("name", "")
        lang_color = lang.get("color", THEME["icon"])

        # Rank badge based on stars
        if stars >= 10000:
            rank, rank_color = "S", THEME["rank_s"]
        elif stars >= 1000:
            rank, rank_color = "A", THEME["rank_a"]
        else:
            rank, rank_color = "B", THEME["rank_b"]

        # Row background (alternating subtle stripe)
        if i % 2 == 1:
            lines.append(f'  <rect x="1" y="{y_base - 16}" width="{card_width - 2}" height="{row_height}" fill="rgba(255,255,255,0.02)"/>')

        # Clickable link wrapping the entire row
        repo_url = f"https://github.com/{name}"
        lines.append(f'  <a xlink:href="{repo_url}" target="_blank">')

        # Rank badge
        lines.append(f'    <g transform="translate(20, {y_base - 10})">')
        lines.append(f'      <rect rx="3" width="22" height="18" fill="{rank_color}" opacity="0.2"/>')
        lines.append(f'      <text x="11" y="13" fill="{rank_color}" font-family="\'Segoe UI\', Sans-Serif" font-size="11" font-weight="600" text-anchor="middle">{rank}</text>')
        lines.append(f'    </g>')

        # Repo name
        lines.append(f'    <text x="52" y="{y_base}" fill="{THEME["link"]}" font-family="\'Segoe UI\', Sans-Serif" font-size="14" font-weight="600">{escape_xml(name)}</text>')

        # Star count with icon
        star_x = 420
        lines.append(f'    <g transform="translate({star_x}, {y_base - 11})">')
        lines.append(f'      <svg width="14" height="14" viewBox="0 0 16 16" fill="{THEME["star"]}"><path d="{star_icon}"/></svg>')
        lines.append(f'    </g>')
        lines.append(f'    <text x="{star_x + 18}" y="{y_base}" fill="{THEME["star"]}" font-family="\'Segoe UI\', Sans-Serif" font-size="12" font-weight="500">{format_stars(stars)}</text>')

        # Language dot + name
        if lang_name:
            lang_x = 490
            lines.append(f'    <circle cx="{lang_x}" cy="{y_base - 4}" r="5" fill="{lang_color}"/>')
            lines.append(f'    <text x="{lang_x + 10}" y="{y_base}" fill="{THEME["icon"]}" font-family="\'Segoe UI\', Sans-Serif" font-size="11">{escape_xml(lang_name)}</text>')

        # Description
        if desc:
            lines.append(f'    <text x="52" y="{y_base + 16}" fill="{THEME["text"]}" font-family="\'Segoe UI\', Sans-Serif" font-size="11" opacity="0.7">{desc}</text>')

        lines.append(f'  </a>')

    lines.append("</svg>")
    return "\n".join(lines)


def main():
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN or METRICS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching contributed repositories for {USERNAME}...")
    repos = query_github(GITHUB_TOKEN, USERNAME)
    print(f"Found {len(repos)} contributed repositories")

    repos = [r for r in repos if r["stargazerCount"] > 0]
    repos.sort(key=lambda r: r["stargazerCount"], reverse=True)

    svg = generate_svg(repos, LIMIT)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Generated {OUTPUT} with top {min(LIMIT, len(repos))} repositories")


if __name__ == "__main__":
    main()
