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

# onedark theme (matches github-readme-stats onedark)
THEME = {
    "bg": "#282c34",
    "title": "#e4e2e2",
    "text": "#adbac7",
    "icon": "#79dafa",
    "link": "#58a6ff",
    "star": "#e3b341",
    "muted": "#7f848e",
    "border": "#3e4451",
    "row_hover": "rgba(255,255,255,0.03)",
}

GRAPHQL_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositoriesContributedTo(
      first: 100
      after: $after
      contributionTypes: [COMMIT]
      includeUserRepositories: false
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      nodes {
        nameWithOwner
        stargazerCount
        description
        primaryLanguage { name color }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

STAR_ICON = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
CONTRIB_ICON = "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

# Per-character width lookup table (ported from github-readme-stats)
# see: https://github.com/anuraghazra/github-readme-stats/blob/master/src/common/render.js
CHAR_WIDTHS = [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0.2796875, 0.2765625,
    0.3546875, 0.5546875, 0.5546875, 0.8890625, 0.665625, 0.190625,
    0.3328125, 0.3328125, 0.3890625, 0.5828125, 0.2765625, 0.3328125,
    0.2765625, 0.3015625, 0.5546875, 0.5546875, 0.5546875, 0.5546875,
    0.5546875, 0.5546875, 0.5546875, 0.5546875, 0.5546875, 0.5546875,
    0.2765625, 0.2765625, 0.584375, 0.5828125, 0.584375, 0.5546875,
    1.0140625, 0.665625, 0.665625, 0.721875, 0.721875, 0.665625,
    0.609375, 0.7765625, 0.721875, 0.2765625, 0.5, 0.665625,
    0.5546875, 0.8328125, 0.721875, 0.7765625, 0.665625, 0.7765625,
    0.721875, 0.665625, 0.609375, 0.721875, 0.665625, 0.94375,
    0.665625, 0.665625, 0.609375, 0.2765625, 0.3546875, 0.2765625,
    0.4765625, 0.5546875, 0.3328125, 0.5546875, 0.5546875, 0.5,
    0.5546875, 0.5546875, 0.2765625, 0.5546875, 0.5546875, 0.221875,
    0.240625, 0.5, 0.221875, 0.8328125, 0.5546875, 0.5546875,
    0.5546875, 0.5546875, 0.3328125, 0.5, 0.2765625, 0.5546875,
    0.5, 0.721875, 0.5, 0.5, 0.5, 0.3546875, 0.259375, 0.353125, 0.5890625,
]
AVG_CHAR_WIDTH = 0.5279276315789471


def measure_text(text, font_size=10):
    """Precisely measure text width using per-character lookup table."""
    total = 0
    for c in text:
        code = ord(c)
        w = CHAR_WIDTHS[code] if code < len(CHAR_WIDTHS) else AVG_CHAR_WIDTH
        total += w
    return total * font_size


def query_github(token, login):
    all_repos = []
    cursor = None
    while True:
        variables = {"login": login}
        if cursor:
            variables["after"] = cursor
        payload = json.dumps({"query": GRAPHQL_QUERY, "variables": variables}).encode()
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
        contrib = data["data"]["user"]["repositoriesContributedTo"]
        all_repos.extend(contrib["nodes"])
        page_info = contrib["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
    return all_repos


def format_stars(count):
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


def escape_xml(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def truncate(text, max_len=60):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def generate_svg(repos):
    """Generate an SVG card matching github-readme-stats style."""
    card_width = 830
    padding_x = 25
    padding_y = 35
    row_height = 50
    title_height = padding_y + 20
    card_height = title_height + len(repos) * row_height + 15
    icon_size = 16
    gap = 25

    css = f"""
    <style>
      .header {{ font: 600 18px {FONT}; fill: {THEME["title"]}; }}
      @supports(-moz-appearance: auto) {{ .header {{ font-size: 15.5px; }} }}
      .repo-name {{ font: 600 13px {FONT}; fill: {THEME["link"]}; }}
      .description {{ font: 400 12px {FONT}; fill: {THEME["text"]}; opacity: 0.7; }}
      .gray {{ font: 400 12px {FONT}; fill: {THEME["muted"]}; }}
      .star-text {{ font: 400 12px {FONT}; fill: {THEME["star"]}; }}
      .icon {{ fill: {THEME["icon"]}; }}
      .star-icon {{ fill: {THEME["star"]}; }}
      .divider {{ stroke: {THEME["border"]}; stroke-width: 0.5; opacity: 0.5; }}
    </style>"""

    L = []  # noqa: E741
    L.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{card_width}" height="{card_height}" '
             f'viewBox="0 0 {card_width} {card_height}" fill="none" role="img" '
             f'aria-labelledby="titleId">')
    L.append(f'  <title id="titleId">Top Contributed Repositories</title>')
    L.append(css)

    # Card background
    L.append(f'  <rect data-testid="card-bg" x="0.5" y="0.5" rx="4.5" '
             f'width="{card_width - 1}" height="{card_height - 1}" '
             f'fill="{THEME["bg"]}" stroke="{THEME["border"]}"/>')

    # Title with prefix icon
    L.append(f'  <g transform="translate({padding_x}, {padding_y})">')
    L.append(f'    <svg class="icon" x="0" y="-13" viewBox="0 0 16 16" width="{icon_size}" height="{icon_size}">')
    L.append(f'      <path fill-rule="evenodd" d="{CONTRIB_ICON}"/>')
    L.append(f'    </svg>')
    L.append(f'    <text x="{icon_size + 9}" y="0" class="header">Top Contributed Repositories</text>')
    L.append(f'  </g>')

    for i, repo in enumerate(repos):
        row_y = title_height + i * row_height
        y_text = row_y + 20

        name = repo["nameWithOwner"]
        stars = format_stars(repo["stargazerCount"])
        desc = escape_xml(truncate(repo.get("description") or "", 105))
        lang = repo.get("primaryLanguage") or {}
        lang_name = lang.get("name", "")
        lang_color = lang.get("color", THEME["muted"])

        # Subtle divider line between rows
        if i > 0:
            L.append(f'  <line class="divider" x1="{padding_x}" y1="{row_y}" '
                     f'x2="{card_width - padding_x}" y2="{row_y}"/>')

        # Repo name (left)
        L.append(f'  <text x="{padding_x}" y="{y_text}" class="repo-name">{escape_xml(name)}</text>')

        # Right-aligned: language + stars using precise measurement
        # Build from right to left
        right_edge = card_width - padding_x

        # Star icon (far right)
        star_icon_x = right_edge - icon_size
        L.append(f'  <g transform="translate({star_icon_x}, {y_text - 12})">'
                 f'<svg class="star-icon" viewBox="0 0 16 16" width="{icon_size}" height="{icon_size}">'
                 f'<path d="{STAR_ICON}"/></svg></g>')

        # Star count (left of icon)
        star_text_w = measure_text(stars, 12)
        star_text_x = star_icon_x - 4  # 4px gap
        L.append(f'  <text x="{star_text_x}" y="{y_text}" class="star-text" text-anchor="end">{stars}</text>')

        # Language dot + name (left of stars)
        if lang_name:
            lang_text_w = measure_text(lang_name, 12)
            lang_block_start = star_text_x - star_text_w - gap
            lang_text_x = lang_block_start  # text-anchor="end"
            dot_x = lang_text_x - lang_text_w - 8
            L.append(f'  <circle cx="{dot_x}" cy="{y_text - 5}" r="5" fill="{lang_color}"/>')
            L.append(f'  <text x="{dot_x + 10}" y="{y_text}" class="gray">{escape_xml(lang_name)}</text>')

        # Description (second line)
        if desc:
            L.append(f'  <text x="{padding_x}" y="{y_text + 18}" class="description">{desc}</text>')

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
        desc = truncate(repo.get("description") or "", 100)
        url = f"https://github.com/{name}"
        lines.append(f"| [**{name}**]({url}) | {stars} | {lang} | {desc} |")
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
