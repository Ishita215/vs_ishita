#!/usr/bin/env python3
"""Analyze a GitHub profile and refresh the generated section of README.md.

Usage:
    GITHUB_TOKEN=xxx USERNAME=Yash-Choubey09 python scripts/analyze_github.py
    python scripts/analyze_github.py --mock --readme /tmp/README.md

The analyzer uses only the Python standard library. A token is optional for
public profiles, but the workflow token avoids GitHub's unauthenticated rate
limit.
"""
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

START = "<!-- GITHUB_ANALYSIS_START -->"
END = "<!-- GITHUB_ANALYSIS_END -->"
API = "https://api.github.com"


def request_json(path, token=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-profile-analyzer"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{API}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"GitHub API request failed ({error.code}) for {path}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach GitHub for {path}: {error.reason}") from error


def fetch_profile(login, token):
    profile = request_json(f"/users/{urllib.parse.quote(login)}", token)
    repos = []
    page = 1
    while True:
        batch = request_json(
            f"/users/{urllib.parse.quote(login)}/repos?per_page=100&page={page}&type=owner&sort=updated",
            token,
        )
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return profile, repos


def mock_profile():
    return (
        {"login": "demo", "name": "Demo Developer", "bio": "Building useful software", "followers": 12, "public_repos": 4},
        [
            {"name": "api-service", "html_url": "https://github.com/demo/api-service", "description": "A Java REST API", "language": "Java", "stargazers_count": 4, "forks_count": 1, "topics": ["spring", "rest-api"], "fork": False, "archived": False, "updated_at": "2026-01-03T00:00:00Z"},
            {"name": "dashboard", "html_url": "https://github.com/demo/dashboard", "description": "React dashboard", "language": "TypeScript", "stargazers_count": 2, "forks_count": 0, "topics": ["react", "frontend"], "fork": False, "archived": False, "updated_at": "2025-12-03T00:00:00Z"},
        ],
    )


def clean(text, limit=180):
    value = re.sub(r"\s+", " ", text or "").strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def analyze(profile, repos):
    original = [repo for repo in repos if not repo.get("fork") and not repo.get("archived")]
    languages = Counter(repo.get("language") for repo in original if repo.get("language"))
    topics = Counter(topic for repo in original for topic in repo.get("topics", []))
    featured = sorted(
        original,
        key=lambda repo: (repo.get("stargazers_count", 0), repo.get("forks_count", 0), repo.get("updated_at", "")),
        reverse=True,
    )[:5]
    return {"profile": profile, "repos": original, "languages": languages, "topics": topics, "featured": featured}


def badge(label, color="2f81f7"):
    encoded = urllib.parse.quote(label.replace(" ", "-"))
    return f"![{label}](https://img.shields.io/badge/{encoded}-{color}?style=flat-square)"


def render(data):
    profile = data["profile"]
    languages = data["languages"]
    topics = data["topics"]
    featured = data["featured"]
    name = profile.get("name") or profile.get("login")
    bio = clean(profile.get("bio"))
    language_badges = " ".join(badge(language) for language, _ in languages.most_common(8)) or "No language data yet"
    topic_badges = " ".join(badge(topic, "7c3aed") for topic, _ in topics.most_common(8))

    lines = [
        START,
        "## GitHub Analysis",
        "",
        f"This section is generated from **{profile.get('login', 'this account')}'s** public GitHub repositories and profile data.",
        "",
        f"> {bio}" if bio else "> Profile bio not provided on GitHub.",
        "",
        f"**{len(data['repos'])}** original public repositories · **{profile.get('followers', 0)}** followers · **{profile.get('following', 0)}** following",
        "",
        "### Repository Language Signals",
        "",
        language_badges,
        "",
    ]
    if languages:
        lines.append("Most-used languages by repository count: " + ", ".join(f"**{language}** ({count})" for language, count in languages.most_common(8)) + ".")
        lines.extend(["", "### Project Topics", "", topic_badges or "No repository topics have been added yet.", ""])
    else:
        lines.extend(["No public repositories with language metadata were found yet.", ""])
    lines.extend(["### Featured Projects", ""])
    if featured:
        for repo in featured:
            details = clean(repo.get("description"), 140) or "No description provided."
            lines.append(f"- [{repo['name']}]({repo['html_url']}) - {details} ({repo.get('language') or 'language not specified'}, {repo.get('stargazers_count', 0)} stars)")
    else:
        lines.append("No public projects are available to feature yet.")
    lines.extend(["", "_Updated automatically from GitHub._", END])
    return "\n".join(lines)


def update_readme(path, section):
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if pattern.search(content):
        content = pattern.sub(section, content, count=1)
    else:
        content = content.rstrip() + "\n\n" + section + "\n"
    path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", default="README.md", help="README file to update")
    parser.add_argument("--mock", action="store_true", help="use local sample data")
    args = parser.parse_args()
    login = os.environ.get("USERNAME", "Yash-Choubey09")
    if args.mock:
        profile, repos = mock_profile()
    else:
        profile, repos = fetch_profile(login, os.environ.get("GITHUB_TOKEN"))
    update_readme(Path(args.readme), render(analyze(profile, repos)))
    print(f"analyzed {profile.get('login', login)}: {len(repos)} repositories; updated {args.readme}")


if __name__ == "__main__":
    main()
