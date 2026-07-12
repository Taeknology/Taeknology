#!/usr/bin/env python3
"""Update the profile README with recent merged external pull requests."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GRAPHQL_URL = "https://api.github.com/graphql"
PROJECT_START = "<!-- OSS-PROJECT-LIST:START -->"
PROJECT_END = "<!-- OSS-PROJECT-LIST:END -->"
PR_START = "<!-- OSS-PR-LIST:START -->"
PR_END = "<!-- OSS-PR-LIST:END -->"
DISPLAY_NAMES = {
    "valkey-io/valkey": "Valkey",
    "python/cpython": "CPython",
    "Yeachan-Heo/oh-my-claudecode": "oh-my-claudecode",
}
EXCLUDED_REPOSITORIES = {"gianters/calculator"}
FEATURED_REPOSITORIES = {"python/cpython", "valkey-io/valkey"}

QUERY = """
query RecentMergedPullRequests($query: String!, $cursor: String) {
  search(query: $query, type: ISSUE, first: 100, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on PullRequest {
        number
        title
        url
        mergedAt
        repository {
          name
          nameWithOwner
          url
          stargazerCount
          owner {
            login
          }
        }
      }
    }
  }
}
"""


def graphql(token: str, variables: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Taeknology-profile-readme",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"GitHub GraphQL request failed: {error.code} {detail}") from error

    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
    return payload["data"]["search"]


def fetch_pull_requests(token: str, username: str) -> list[dict[str, Any]]:
    search_query = f"author:{username} is:pr is:merged"
    cursor = None
    pull_requests: list[dict[str, Any]] = []

    while True:
        result = graphql(token, {"query": search_query, "cursor": cursor})
        pull_requests.extend(node for node in result["nodes"] if node and node.get("mergedAt"))
        page_info = result["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    return pull_requests


def select_activity(
    pull_requests: list[dict[str, Any]], username: str, recent_count: int = 5
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    external = [
        pull_request
        for pull_request in pull_requests
        if pull_request["repository"]["owner"]["login"].casefold() != username.casefold()
        and pull_request["repository"]["nameWithOwner"] not in EXCLUDED_REPOSITORIES
    ]
    external.sort(key=lambda pull_request: pull_request["mergedAt"], reverse=True)

    projects_by_name: dict[str, dict[str, Any]] = {}
    for pull_request in external:
        repository = pull_request["repository"]
        projects_by_name.setdefault(repository["nameWithOwner"], repository)

    projects = sorted(
        projects_by_name.values(),
        key=lambda repository: (
            repository["nameWithOwner"] not in FEATURED_REPOSITORIES,
            -repository["stargazerCount"],
            repository["nameWithOwner"].casefold(),
        ),
    )

    return projects, external[:recent_count]


def markdown_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def project_name(repository: dict[str, Any]) -> str:
    return DISPLAY_NAMES.get(repository["nameWithOwner"], repository["name"])


def render_projects(projects: list[dict[str, Any]]) -> str:
    if not projects:
        return "_No merged external contributions._"
    return " · ".join(
        f"[{markdown_escape(project_name(repository))}]({repository['url']})"
        for repository in projects
    )


def render_pull_requests(pull_requests: list[dict[str, Any]]) -> str:
    if not pull_requests:
        return "_No recently merged external pull requests._"
    return "\n".join(
        f"- [{markdown_escape(project_name(pull_request['repository']))} "
        f"#{pull_request['number']}]({pull_request['url']}) — "
        f"{markdown_escape(pull_request['title'])}"
        for pull_request in pull_requests
    )


def replace_block(document: str, start: str, end: str, content: str) -> str:
    start_index = document.find(start)
    end_index = document.find(end)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise ValueError(f"README marker pair not found: {start} / {end}")
    content_start = start_index + len(start)
    return document[:content_start] + "\n" + content.strip() + "\n" + document[end_index:]


def update_readme(
    readme: str, projects: list[dict[str, Any]], pull_requests: list[dict[str, Any]]
) -> str:
    readme = replace_block(readme, PROJECT_START, PROJECT_END, render_projects(projects))
    return replace_block(readme, PR_START, PR_END, render_pull_requests(pull_requests))


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    username = os.environ.get("GITHUB_REPOSITORY_OWNER", "Taeknology")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 2

    pull_requests = fetch_pull_requests(token, username)
    projects, recent = select_activity(pull_requests, username)

    readme_path = Path("README.md")
    original = readme_path.read_text()
    updated = update_readme(original, projects, recent)
    if updated != original:
        readme_path.write_text(updated)
        print(f"Updated {readme_path} with {len(projects)} projects and {len(recent)} pull requests")
    else:
        print("README is already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
