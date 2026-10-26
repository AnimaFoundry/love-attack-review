"""Publish the fixed v1.3.0 companion after the workflow's green main-branch CI.

Copyright (c) 2026 AnimaFoundry. MIT; see ../LICENSE-CODE.
The workflow must make this job depend on successful offline Ubuntu validation.
GITHUB_TOKEN-created tags may not trigger another workflow: do not claim tag CI.
This helper verifies that the tag resolves to the already checked exact commit.
It never uploads an archive or asset, changes a branch, or follows redirects.
"""
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import re
import sys

REPOSITORY = "AnimaFoundry/love-attack-review"
TAG = "v1.3.0"
TITLE = "BF-01C task-only feasibility companion v1.3.0"
API_HOST = "api.github.com"
PREFIX = "/repos/" + REPOSITORY
RELEASE_URL = "https://github.com/" + REPOSITORY + "/releases/tag/" + TAG
_SHA = re.compile(r"[0-9a-f]{40}")
MAX_RESPONSE_BYTES = 1_048_576


class PublishError(RuntimeError):
    """Static non-sensitive diagnostic; never contains headers or response bodies."""


def _require(condition, diagnostic):
    if not condition:
        raise PublishError(diagnostic)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_member")
        result[key] = value
    return result


class GitHubAPI:
    """A fixed-host HTTPS client with no redirect handling or logging."""
    def __init__(self, token):
        _require(type(token) is str and bool(token.strip()) and "\r" not in token and "\n" not in token,
                 "missing_or_invalid_workflow_token")
        self._token = token

    def __call__(self, method, path, payload=None, *, allow_missing=False):
        _require(method in {"GET", "POST"}, "unsupported_http_method")
        allowed_get = (
            path in {PREFIX + "/git/ref/heads/main", PREFIX + "/git/ref/tags/" + TAG,
                     PREFIX + "/releases/tags/" + TAG}
            or (path.startswith(PREFIX + "/git/tags/") and
                _SHA.fullmatch(path.removeprefix(PREFIX + "/git/tags/")) is not None)
        )
        _require((method == "GET" and allowed_get and payload is None) or
                 (method == "POST" and path == PREFIX + "/releases" and type(payload) is dict),
                 "endpoint_not_allowed")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + self._token,
                   "User-Agent": "AnimaFoundry-BF01C-release-helper", "X-GitHub-Api-Version": "2022-11-28"}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        connection = http.client.HTTPSConnection(API_HOST, timeout=30)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, http.client.HTTPException):
            raise PublishError("github_transport_failed_no_automatic_retry") from None
        finally:
            connection.close()
        _require(len(raw) <= MAX_RESPONSE_BYTES, "github_response_too_large")
        if status == 404 and allow_missing:
            return None
        _require(status == (200 if method == "GET" else 201), "github_status_rejected_no_redirect_or_retry")
        try:
            result = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs)
        except (ValueError, UnicodeError):
            raise PublishError("invalid_github_response_json") from None
        _require(type(result) is dict, "github_response_object_required")
        return result


def _main_commit(api, expected_sha):
    value = api("GET", PREFIX + "/git/ref/heads/main")
    _require(type(value) is dict and value.get("ref") == "refs/heads/main", "main_reference_mismatch")
    obj = value.get("object")
    _require(type(obj) is dict and obj.get("type") == "commit" and obj.get("sha") == expected_sha,
             "main_no_longer_matches_checked_commit")


def _tag_commit(api, tag_reference):
    _require(type(tag_reference) is dict and tag_reference.get("ref") == "refs/tags/" + TAG,
             "tag_reference_mismatch")
    obj = tag_reference.get("object")
    seen = set()
    for _ in range(5):
        _require(type(obj) is dict and type(obj.get("sha")) is str and _SHA.fullmatch(obj["sha"]) is not None,
                 "invalid_tag_object")
        sha = obj["sha"]
        if obj.get("type") == "commit":
            return sha
        _require(obj.get("type") == "tag" and sha not in seen, "unsupported_or_cyclic_tag_object")
        seen.add(sha)
        value = api("GET", PREFIX + "/git/tags/" + sha)
        _require(type(value) is dict and value.get("sha") == sha, "annotated_tag_object_mismatch")
        obj = value.get("object")
    raise PublishError("tag_indirection_limit")


def _release_matches(value, expected_sha, notes):
    _require(type(value) is dict and value.get("tag_name") == TAG, "release_tag_mismatch")
    _require(value.get("target_commitish") == expected_sha, "release_target_mismatch")
    _require(value.get("draft") is False and value.get("prerelease") is False, "release_visibility_mismatch")
    _require(value.get("name") == TITLE and value.get("body") == notes, "existing_release_content_mismatch")
    _require(value.get("html_url") == RELEASE_URL, "release_url_mismatch")
    _require(type(value.get("id")) is int and value["id"] > 0, "invalid_release_identity")


def publish(environment, notes, api):
    """Perform fixed-scope publication; dependency-injected API permits offline tests.

    Existing matching releases are read and verified without mutation. Existing
    conflicting tags/releases fail closed. A failure after creation requires
    remote inspection; it does not authorize deleting or replacing the release.
    """
    _require(environment.get("GITHUB_REPOSITORY") == REPOSITORY, "repository_not_allowed")
    _require(environment.get("GITHUB_REF") == "refs/heads/main", "main_branch_required")
    _require(environment.get("GITHUB_EVENT_NAME") in {"push", "workflow_dispatch"}, "event_not_allowed")
    _require(environment.get("GITHUB_ACTIONS") == "true", "workflow_environment_required")
    sha = environment.get("GITHUB_SHA")
    _require(type(sha) is str and _SHA.fullmatch(sha) is not None, "exact_checked_commit_required")
    _require(type(notes) is str and bool(notes.strip()) and len(notes.encode("utf-8")) <= 100_000,
             "nonempty_bounded_release_notes_required")
    _main_commit(api, sha)
    tag = api("GET", PREFIX + "/git/ref/tags/" + TAG, allow_missing=True)
    if tag is not None:
        _require(_tag_commit(api, tag) == sha, "existing_tag_points_to_different_commit")
    release = api("GET", PREFIX + "/releases/tags/" + TAG, allow_missing=True)
    created = False
    if release is not None:
        _require(tag is not None, "release_without_matching_tag")
        _release_matches(release, sha, notes)
    else:
        # Recheck immediately before mutation; the release target is the exact
        # tested commit even if main advances after this check.
        _main_commit(api, sha)
        release = api("POST", PREFIX + "/releases", {
            "tag_name": TAG, "target_commitish": sha, "name": TITLE, "body": notes,
            "draft": False, "prerelease": False, "generate_release_notes": False,
        })
        created = True
        _release_matches(release, sha, notes)
    verified_tag = api("GET", PREFIX + "/git/ref/tags/" + TAG)
    _require(_tag_commit(api, verified_tag) == sha, "published_tag_commit_mismatch")
    verified_release = api("GET", PREFIX + "/releases/tags/" + TAG)
    _release_matches(verified_release, sha, notes)
    _require(verified_release["id"] == release["id"], "release_identity_changed")
    return {"status": "created_and_verified" if created else "existing_matching_release_verified",
            "repository": REPOSITORY, "tag": TAG, "commit": sha, "release_url": RELEASE_URL,
            "release_id": verified_release["id"],
            "validation_scope": "Same exact commit as required upstream main-branch validation; no separate tag-CI claim."}


def main():
    notes_path = Path(__file__).resolve().parents[1] / "RELEASE_NOTES.md"
    try:
        notes = notes_path.read_text(encoding="utf-8")
        token = os.environ.get("GITHUB_TOKEN")
        result = publish(os.environ, notes, GitHubAPI(token))
    except (PublishError, OSError, UnicodeError) as exc:
        diagnostic = str(exc) if isinstance(exc, PublishError) else "release_input_read_failed"
        print(json.dumps({"status": "stopped", "reason": diagnostic}), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
