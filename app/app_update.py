"""Read-only application update checks against stable GitHub Releases."""
import re
from typing import Any, Dict, Optional, Tuple

import requests

from . import __version__

LATEST_RELEASE_URL = "https://api.github.com/repos/marinfrankovic/WP_Updater/releases/latest"
CONNECTOR_ASSET_NAME = "wp-updater-connector.php"
CONNECTOR_VERSION_PATTERN = re.compile(
    r"define\(\s*['\"]WPUPDATER_VERSION['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
)
UPDATE_COMMANDS = {
    "publishedImage": [
        "docker compose pull wp-updater",
        "docker compose up -d --no-deps wp-updater",
    ],
    "sourceBuild": [
        "git pull",
        "docker compose up -d --build wp-updater",
    ],
}


def _parse_version(value: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not value:
        return None
    normalized = value.strip().lstrip("vV").split("-", 1)[0].split("+", 1)[0]
    parts = normalized.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    return tuple((numbers + [0, 0])[:3])


def current_info() -> Dict[str, Any]:
    return {
        "currentVersion": __version__,
        "commands": UPDATE_COMMANDS,
    }


def check_for_update() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "currentVersion": __version__,
        "latestVersion": None,
        "updateAvailable": False,
        "releaseName": None,
        "releaseNotes": None,
        "releaseUrl": None,
        "latestConnectorVersion": None,
        "connectorDownloadUrl": None,
        "connectorError": None,
        "commands": UPDATE_COMMANDS,
        "error": None,
    }
    try:
        response = requests.get(
            LATEST_RELEASE_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"WP-Updater/{__version__}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=15,
        )
        if response.status_code == 404:
            result["error"] = "No published release is available yet."
            return result
        response.raise_for_status()
        release = response.json()
    except requests.Timeout:
        result["error"] = "The update check timed out."
        return result
    except (requests.RequestException, ValueError) as exc:
        result["error"] = f"Update check failed: {exc}"
        return result

    latest = _parse_version(release.get("tag_name"))
    current = _parse_version(__version__)
    if latest is None or current is None:
        result["error"] = "The latest release has an invalid version tag."
        return result

    result.update({
        "latestVersion": ".".join(str(part) for part in latest),
        "updateAvailable": latest > current,
        "releaseName": release.get("name"),
        "releaseNotes": release.get("body"),
        "releaseUrl": release.get("html_url"),
    })

    connector_asset = next(
        (
            asset for asset in (release.get("assets") or [])
            if asset.get("name") == CONNECTOR_ASSET_NAME
        ),
        None,
    )
    if connector_asset is None or not connector_asset.get("browser_download_url"):
        result["connectorError"] = "The latest release does not include the connector asset."
        return result

    result["connectorDownloadUrl"] = connector_asset["browser_download_url"]
    try:
        connector_response = requests.get(
            result["connectorDownloadUrl"],
            headers={"User-Agent": f"WP-Updater/{__version__}"},
            timeout=15,
        )
        connector_response.raise_for_status()
    except requests.Timeout:
        result["connectorError"] = "The connector update check timed out."
        return result
    except requests.RequestException as exc:
        result["connectorError"] = f"Connector update check failed: {exc}"
        return result

    version_match = CONNECTOR_VERSION_PATTERN.search(connector_response.text)
    connector_version = _parse_version(version_match.group(1) if version_match else None)
    if connector_version is None:
        result["connectorError"] = "The connector asset has an invalid version."
        return result
    result["latestConnectorVersion"] = ".".join(str(part) for part in connector_version)
    return result