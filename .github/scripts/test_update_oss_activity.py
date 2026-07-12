#!/usr/bin/env python3

import unittest

from update_oss_activity import select_activity, update_readme


def pull_request(repo, owner, number, merged_at):
    return {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/{repo}/pull/{number}",
        "mergedAt": merged_at,
        "repository": {
            "name": repo.split("/")[-1],
            "nameWithOwner": repo,
            "url": f"https://github.com/{repo}",
            "owner": {"login": owner},
        },
    }


class UpdateOssActivityTest(unittest.TestCase):
    def test_projects_are_unique_but_recent_pull_requests_allow_duplicates(self):
        pull_requests = [
            pull_request("valkey-io/valkey", "valkey-io", 6, "2026-07-11T00:00:00Z"),
            pull_request("valkey-io/valkey", "valkey-io", 5, "2026-07-10T00:00:00Z"),
            pull_request("python/cpython", "python", 4, "2026-07-09T00:00:00Z"),
            pull_request("python/cpython", "python", 3, "2026-07-08T00:00:00Z"),
            pull_request("example/project", "example", 2, "2026-07-07T00:00:00Z"),
            pull_request("example/project", "example", 1, "2026-07-06T00:00:00Z"),
            pull_request("Taeknology/owned", "Taeknology", 4, "2026-07-12T00:00:00Z"),
        ]

        projects, recent = select_activity(pull_requests, "Taeknology")

        self.assertEqual(
            [project["nameWithOwner"] for project in projects],
            ["valkey-io/valkey", "python/cpython", "example/project"],
        )
        self.assertEqual([pull_request["number"] for pull_request in recent], [6, 5, 4, 3, 2])

    def test_readme_marker_blocks_are_replaced(self):
        readme = """projects
<!-- OSS-PROJECT-LIST:START -->
old
<!-- OSS-PROJECT-LIST:END -->
prs
<!-- OSS-PR-LIST:START -->
old
<!-- OSS-PR-LIST:END -->
"""
        pull_requests = [
            pull_request("valkey-io/valkey", "valkey-io", 2, "2026-07-11T00:00:00Z")
        ]
        projects, recent = select_activity(pull_requests, "Taeknology")

        updated = update_readme(readme, projects, recent)

        self.assertIn("[Valkey](https://github.com/valkey-io/valkey)", updated)
        self.assertIn("[Valkey #2](https://github.com/valkey-io/valkey/pull/2)", updated)
        self.assertNotIn("\nold\n", updated)


if __name__ == "__main__":
    unittest.main()
