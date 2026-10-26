"""Mocked fixed-scope release-helper regressions; never contact GitHub.

Copyright (c) 2026 AnimaFoundry. MIT; see ../LICENSE-CODE.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publish_companion", ROOT / "scripts/publish_companion.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)
SHA = "a" * 40
OTHER = "b" * 40
NOTES = "Original synthetic BF-01C companion.\n"


def reference(kind, sha=SHA, obj_type="commit"):
    return {"ref": "refs/" + kind, "object": {"type": obj_type, "sha": sha}}


def release(sha=SHA):
    return {"id": 31, "tag_name": publisher.TAG, "target_commitish": sha,
            "name": publisher.TITLE, "body": NOTES, "draft": False, "prerelease": False,
            "html_url": publisher.RELEASE_URL}


class FakeAPI:
    def __init__(self, tag=None, existing=None):
        self.tag = copy.deepcopy(tag)
        self.release = copy.deepcopy(existing)
        self.main = reference("heads/main")
        self.calls = []
        self.annotations = {}

    def __call__(self, method, path, payload=None, *, allow_missing=False):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == "POST":
            self.release = release(payload["target_commitish"])
            self.tag = reference("tags/" + publisher.TAG, payload["target_commitish"])
            return copy.deepcopy(self.release)
        if path.endswith("/git/ref/heads/main"):
            return copy.deepcopy(self.main)
        if path.endswith("/git/ref/tags/" + publisher.TAG):
            return copy.deepcopy(self.tag)
        if path.endswith("/releases/tags/" + publisher.TAG):
            return copy.deepcopy(self.release)
        if "/git/tags/" in path:
            return copy.deepcopy(self.annotations[path.rsplit("/", 1)[1]])
        raise AssertionError("Unexpected mocked endpoint")


class PublishControls(unittest.TestCase):
    def setUp(self):
        self.env = {"GITHUB_REPOSITORY": publisher.REPOSITORY, "GITHUB_REF": "refs/heads/main",
                    "GITHUB_SHA": SHA, "GITHUB_EVENT_NAME": "push", "GITHUB_ACTIONS": "true"}

    def test_creates_fixed_release_and_verifies_exact_tag(self):
        api = FakeAPI()
        result = publisher.publish(self.env, NOTES, api)
        self.assertEqual(result["status"], "created_and_verified")
        posts = [c for c in api.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1], publisher.PREFIX + "/releases")
        self.assertEqual(posts[0][2]["target_commitish"], SHA)
        self.assertEqual(posts[0][2]["tag_name"], "v1.3.0")
        self.assertEqual(posts[0][2]["body"], NOTES)
        self.assertNotIn("assets", posts[0][2])

    def test_matching_release_is_idempotent_read_only(self):
        api = FakeAPI(reference("tags/" + publisher.TAG), release())
        result = publisher.publish(self.env, NOTES, api)
        self.assertEqual(result["status"], "existing_matching_release_verified")
        self.assertFalse(any(c[0] == "POST" for c in api.calls))

    def test_matching_existing_tag_without_release_can_publish(self):
        api = FakeAPI(reference("tags/" + publisher.TAG))
        self.assertEqual(publisher.publish(self.env, NOTES, api)["commit"], SHA)

    def test_wrong_repository_ref_event_sha_and_environment_fail_before_io(self):
        for field, value in [("GITHUB_REPOSITORY", "other/repository"),
                             ("GITHUB_REF", "refs/pull/1/merge"),
                             ("GITHUB_EVENT_NAME", "pull_request_target"),
                             ("GITHUB_SHA", "main"), ("GITHUB_SHA", "a" * 39),
                             ("GITHUB_ACTIONS", "false")]:
            with self.subTest(field=field):
                env, api = dict(self.env), FakeAPI()
                env[field] = value
                with self.assertRaises(publisher.PublishError):
                    publisher.publish(env, NOTES, api)
                self.assertEqual(api.calls, [])

    def test_empty_notes_fail_before_io(self):
        api = FakeAPI()
        with self.assertRaises(publisher.PublishError):
            publisher.publish(self.env, " ", api)
        self.assertEqual(api.calls, [])

    def test_moved_main_and_wrong_tag_stop_before_mutation(self):
        main_api = FakeAPI()
        main_api.main = reference("heads/main", OTHER)
        for api in (main_api, FakeAPI(reference("tags/" + publisher.TAG, OTHER)),
                    FakeAPI(reference("tags/v1.2.0"))):
            with self.assertRaises(publisher.PublishError):
                publisher.publish(self.env, NOTES, api)
            self.assertFalse(any(c[0] == "POST" for c in api.calls))

    def test_main_is_rechecked_immediately_before_creation(self):
        api = FakeAPI()
        def moving(method, path, payload=None, **kwargs):
            result = api(method, path, payload, **kwargs)
            if path.endswith("/releases/tags/" + publisher.TAG):
                api.main = reference("heads/main", OTHER)
            return result
        with self.assertRaises(publisher.PublishError):
            publisher.publish(self.env, NOTES, moving)
        self.assertFalse(any(c[0] == "POST" for c in api.calls))

    def test_conflicting_existing_release_fields_are_not_overwritten(self):
        for field, value in [("tag_name", "v1.2.0"), ("target_commitish", "main"),
                             ("body", "Different release"), ("draft", True),
                             ("prerelease", True), ("html_url", "https://example.invalid/")]:
            existing = release()
            existing[field] = value
            api = FakeAPI(reference("tags/" + publisher.TAG), existing)
            with self.assertRaises(publisher.PublishError):
                publisher.publish(self.env, NOTES, api)
            self.assertFalse(any(c[0] == "POST" for c in api.calls))

    def test_release_without_tag_is_rejected(self):
        api = FakeAPI(existing=release())
        with self.assertRaises(publisher.PublishError):
            publisher.publish(self.env, NOTES, api)
        self.assertFalse(any(c[0] == "POST" for c in api.calls))

    def test_annotated_tag_is_resolved_and_cycles_rejected(self):
        annotated_sha = "c" * 40
        api = FakeAPI(reference("tags/" + publisher.TAG, annotated_sha, "tag"), release())
        api.annotations[annotated_sha] = {"sha": annotated_sha, "object": {"type": "commit", "sha": SHA}}
        self.assertEqual(publisher.publish(self.env, NOTES, api)["commit"], SHA)
        api.annotations[annotated_sha]["object"] = {"type": "tag", "sha": annotated_sha}
        with self.assertRaises(publisher.PublishError):
            publisher.publish(self.env, NOTES, api)

    def test_post_creation_tag_mismatch_is_not_claimed_success(self):
        api = FakeAPI()
        def corrupting(method, path, payload=None, **kwargs):
            value = api(method, path, payload, **kwargs)
            if method == "POST":
                api.tag = reference("tags/" + publisher.TAG, OTHER)
            return value
        with self.assertRaises(publisher.PublishError):
            publisher.publish(self.env, NOTES, corrupting)
        self.assertEqual(sum(c[0] == "POST" for c in api.calls), 1)

    def test_http_redirects_are_not_followed_and_errors_hide_token(self):
        token = "mock-secret-never-log"
        with patch.object(publisher.http.client, "HTTPSConnection") as factory:
            conn = factory.return_value
            response = conn.getresponse.return_value
            response.status = 302
            response.read.return_value = b'{"error":"mock-secret-never-log"}'
            with self.assertRaises(publisher.PublishError) as caught:
                publisher.GitHubAPI(token)("GET", publisher.PREFIX + "/git/ref/heads/main")
            self.assertNotIn(token, str(caught.exception))
            factory.assert_called_once_with("api.github.com", timeout=30)
            self.assertEqual(conn.request.call_count, 1)
            conn.close.assert_called_once()

    def test_token_and_endpoint_restrictions_prevent_http_calls(self):
        with patch.object(publisher.http.client, "HTTPSConnection") as factory:
            for token in (None, "", "bad\r\nheader"):
                with self.assertRaises(publisher.PublishError):
                    publisher.GitHubAPI(token)
            client = publisher.GitHubAPI("mock-token")
            for method, path in [("GET", "https://other.invalid/"), ("GET", "/user"),
                                 ("POST", publisher.PREFIX + "/git/refs"),
                                 ("DELETE", publisher.PREFIX + "/releases/31")]:
                with self.assertRaises(publisher.PublishError):
                    client(method, path)
            factory.assert_not_called()

    def test_http_missing_and_success_responses_are_bounded_objects(self):
        with patch.object(publisher.http.client, "HTTPSConnection") as factory:
            response = factory.return_value.getresponse.return_value
            response.status, response.read.return_value = 404, b'{}'
            client = publisher.GitHubAPI("mock-token")
            self.assertIsNone(client("GET", publisher.PREFIX + "/releases/tags/" + publisher.TAG, allow_missing=True))
            response.status, response.read.return_value = 200, json.dumps(reference("heads/main")).encode()
            self.assertEqual(client("GET", publisher.PREFIX + "/git/ref/heads/main")["object"]["sha"], SHA)
            response.read.return_value = b'[]'
            with self.assertRaises(publisher.PublishError):
                client("GET", publisher.PREFIX + "/git/ref/heads/main")


if __name__ == "__main__":
    unittest.main()
