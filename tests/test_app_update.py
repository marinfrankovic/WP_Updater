import unittest
from unittest.mock import Mock, patch

import requests

from app import app_update


class AppUpdateTests(unittest.TestCase):
    @patch("app.app_update.requests.get")
    def test_current_info_does_not_contact_github(self, get: Mock) -> None:
        result = app_update.current_info()

        self.assertEqual(app_update.__version__, result["currentVersion"])
        self.assertIn("sourceBuild", result["commands"])
        get.assert_not_called()

    @patch("app.app_update.requests.get")
    def test_newer_stable_release_is_reported(self, get: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "tag_name": "v9.8.7",
            "name": "WP Updater 9.8.7",
            "body": "Release notes",
            "html_url": "https://github.com/example/releases/tag/v9.8.7",
        }
        get.return_value = response

        result = app_update.check_for_update()

        self.assertTrue(result["updateAvailable"])
        self.assertEqual("9.8.7", result["latestVersion"])
        self.assertEqual("Release notes", result["releaseNotes"])
        self.assertEqual([
            "docker compose pull wp-updater",
            "docker compose up -d --no-deps wp-updater",
        ], result["commands"]["publishedImage"])
        self.assertEqual([
            "git pull",
            "docker compose up -d --build wp-updater",
        ], result["commands"]["sourceBuild"])
        self.assertIsNone(result["error"])

    @patch("app.app_update.requests.get")
    def test_connector_version_is_read_from_release_asset(self, get: Mock) -> None:
        release_response = Mock(status_code=200)
        release_response.json.return_value = {
            "tag_name": "v1.7.0",
            "name": "WP Updater 1.7.0",
            "body": "Release notes",
            "html_url": "https://github.com/example/releases/tag/v1.7.0",
            "assets": [{
                "name": "wp-updater-connector.php",
                "browser_download_url": "https://github.com/example/wp-updater-connector.php",
            }],
        }
        connector_response = Mock(status_code=200)
        connector_response.text = "define('WPUPDATER_VERSION', '2.3.4');"
        get.side_effect = [release_response, connector_response]

        result = app_update.check_for_update()

        self.assertEqual("2.3.4", result["latestConnectorVersion"])
        self.assertEqual(
            "https://github.com/example/wp-updater-connector.php",
            result["connectorDownloadUrl"],
        )
        self.assertIsNone(result["connectorError"])

    @patch("app.app_update.requests.get")
    def test_missing_connector_asset_does_not_hide_core_update(self, get: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "tag_name": "v9.8.7",
            "name": "WP Updater 9.8.7",
            "body": "Release notes",
            "html_url": "https://github.com/example/releases/tag/v9.8.7",
            "assets": [],
        }
        get.return_value = response

        result = app_update.check_for_update()

        self.assertTrue(result["updateAvailable"])
        self.assertEqual(
            "The latest release does not include the connector asset.",
            result["connectorError"],
        )

    @patch("app.app_update.requests.get")
    def test_repository_without_releases_returns_safe_message(self, get: Mock) -> None:
        get.return_value = Mock(status_code=404)

        result = app_update.check_for_update()

        self.assertFalse(result["updateAvailable"])
        self.assertEqual("No published release is available yet.", result["error"])

    @patch("app.app_update.requests.get", side_effect=requests.Timeout)
    def test_timeout_returns_safe_message(self, _get: Mock) -> None:
        result = app_update.check_for_update()

        self.assertFalse(result["updateAvailable"])
        self.assertEqual("The update check timed out.", result["error"])

    def test_version_parser_normalizes_release_tags(self) -> None:
        self.assertEqual((1, 2, 3), app_update._parse_version("v1.2.3"))
        self.assertEqual((2, 0, 1), app_update._parse_version("2.0.1-beta.1"))
        self.assertIsNone(app_update._parse_version("release-next"))


if __name__ == "__main__":
    unittest.main()