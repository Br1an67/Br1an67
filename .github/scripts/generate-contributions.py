#!/usr/bin/env python3
"""Generate an HTML table of top contributed repositories, injected into README.md."""

import json
import os
import sys
import urllib.request

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
USERNAME = os.environ.get("USERNAME", "Br1an67")
LIMIT = int(os.environ.get("LIMIT", "0"))  # 0 = show all
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "10"))
README = os.environ.get("README", "README.md")

START_MARKER = "<!-- CONTRIBUTIONS:START -->"
END_MARKER = "<!-- CONTRIBUTIONS:END -->"

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
        primaryLanguage { name }
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


def truncate(text, max_len=60):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def generate_table(repos):
    """Generate an HTML table for a batch of repos."""
    lines = []
    lines.append("<table>")
    lines.append("  <thead>")
    lines.append("    <tr>")
    lines.append('      <th align="left">Repository</th>')
    lines.append('      <th align="center">⭐ Stars</th>')
    lines.append('      <th align="center">Language</th>')
    lines.append('      <th align="left">Description</th>')
    lines.append("    </tr>")
    lines.append("  </thead>")
    lines.append("  <tbody>")

    for repo in repos:
        name = repo["nameWithOwner"]
        stars = format_stars(repo["stargazerCount"])
        lang = (repo.get("primaryLanguage") or {}).get("name", "—")
        desc = truncate(repo.get("description") or "", 60)
        url = f"https://github.com/{name}"

        lines.append("    <tr>")
        lines.append(f'      <td><a href="{url}"><b>{name}</b></a></td>')
        lines.append(f'      <td align="center">{stars}</td>')
        lines.append(f'      <td align="center">{lang}</td>')
        lines.append(f"      <td>{desc}</td>")
        lines.append("    </tr>")

    lines.append("  </tbody>")
    lines.append("</table>")
    return lines


def generate_html(repos, page_size):
    """Generate HTML with first page visible + remaining in collapsible sections."""
    if not repos:
        return ""

    lines = []

    # First page — always visible
    first_page = repos[:page_size]
    lines.extend(generate_table(first_page))

    # Remaining pages — wrapped in <details>
    remaining = repos[page_size:]
    page_num = 2
    while remaining:
        page = remaining[:page_size]
        remaining = remaining[page_size:]
        start = (page_num - 1) * page_size + 1
        end = start + len(page) - 1

        lines.append("")
        lines.append("<details>")
        lines.append(f"  <summary>🔽 Show more ({start}–{end})</summary>")
        lines.append("")
        lines.extend(generate_table(page))
        lines.append("")
        lines.append("</details>")
        page_num += 1

    return "\n".join(lines)


def inject_into_readme(html, readme_path):
    """Replace content between markers in README.md."""
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    start = content.find(START_MARKER)
    end = content.find(END_MARKER)

    if start == -1 or end == -1:
        print(f"Error: markers not found in {readme_path}", file=sys.stderr)
        print(f"Add {START_MARKER} and {END_MARKER} to your README.md", file=sys.stderr)
        sys.exit(1)

    new_content = (
        content[: start + len(START_MARKER)]
        + "\n"
        + html
        + "\n"
        + content[end:]
    )

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

    html = generate_html(repos, PAGE_SIZE)
    inject_into_readme(html, README)
    print(f"Injected {len(repos)} repos into {README} (page size: {PAGE_SIZE})")


if __name__ == "__main__":
    main()
