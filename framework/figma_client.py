"""Figma API integration client."""

import logging
import os
import re
from urllib.parse import unquote
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from pydantic import ValidationError

from framework.models import FigmaDesign

logger = logging.getLogger(__name__)


class FigmaAPIError(Exception):
    """Custom exception for Figma API errors."""

    pass


class FigmaClient:
    """Figma API integration client."""

    BASE_URL = "https://api.figma.com/v1"
    MAX_RETRIES = 5  # Increased from 3 for better rate limit handling
    RETRY_DELAY = 5  # Increased from 2 seconds (Figma rate limit is 300 req/min = 1 req/0.2s)

    def __init__(
        self,
        api_token: str,
        storage_dir: Path = Path("prd"),
        timeout: Optional[int] = None,
    ):
        """Initialize Figma client.

        Args:
            api_token: Figma personal access token.
            storage_dir: Directory to store downloaded screenshots.
            timeout: Request timeout in seconds (defaults to FIGMA_API_TIMEOUT env var or 30).
        """
        self.api_token = api_token
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Increased default timeout from 30s to 120s for large Figma files
        self.timeout = timeout or int(os.getenv("FIGMA_API_TIMEOUT", "120"))

        self.session = requests.Session()
        self.session.headers.update({"X-Figma-Token": self.api_token})

        # Rate limiting: Figma allows 300 requests/minute (1 request/0.2 seconds)
        # Add buffer for safety: 1 request per 0.25 seconds
        self._last_request_time = 0
        self._min_request_interval = 0.25

        logger.info(
            f"Figma client initialized with timeout: {self.timeout}s, "
            f"rate limit: {1/self._min_request_interval:.0f} req/sec"
        )

    def parse_figma_url(self, url: str) -> tuple[str, Optional[str]]:
        """Extract file_key and node_id from Figma URL.

        Supports various Figma URL formats:
        - https://figma.com/design/FILE_KEY/NAME?node-id=NODE_ID
        - https://www.figma.com/file/FILE_KEY/NAME?node-id=NODE_ID
        - https://figma.com/design/FILE_KEY

        Args:
            url: Figma URL.

        Returns:
            Tuple of (file_key, node_id). node_id may be None.

        Raises:
            FigmaAPIError: If URL format is invalid.

        Example:
            >>> client.parse_figma_url("https://figma.com/design/abc123/MyApp?node-id=1-2")
            ("abc123", "1:2")
        """
        # Pattern for file key (alphanumeric string)
        file_key_pattern = r"/(file|design)/([a-zA-Z0-9]+)"
        match = re.search(file_key_pattern, url)

        if not match:
            raise FigmaAPIError(f"Invalid Figma URL format: {url}")

        file_key = match.group(2)

        # Extract node-id if present
        node_id = None
        # Figma writes node ids as either "1-2" or "1:2" depending on where
        # the link was copied from. The character class previously excluded
        # ":", so a colon-form URL matched only the digits before it and
        # "node-id=1:2" silently became "1" — a valid-looking id addressing
        # the wrong node.
        # Percent-decoded first: a URL copied from the browser address bar
        # carries "node-id=123%3A456", where the encoded colon truncated the
        # id to "123".
        decoded_url = unquote(url)
        node_id_match = re.search(r"node-id=([0-9]+[-:][0-9]+|[0-9]+)", decoded_url)
        if node_id_match:
            # The REST API addresses nodes with a colon.
            node_id = node_id_match.group(1).replace("-", ":")

        logger.info(f"Parsed Figma URL: file_key={file_key}, node_id={node_id}")
        return file_key, node_id

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None, retries: int = 0
    ) -> Dict:
        """Make API request with enhanced retry logic for rate limiting.

        Args:
            endpoint: API endpoint path.
            params: Query parameters.
            retries: Current retry count.

        Returns:
            JSON response data.

        Raises:
            FigmaAPIError: If request fails after retries.
        """
        # Enforce minimum interval between requests to avoid rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            wait_time = self._min_request_interval - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.3f}s before next request")
            time.sleep(wait_time)

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            self._last_request_time = time.time()  # Record request time after response
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            # Record request time for failed requests too (for rate limiting)
            self._last_request_time = time.time()
            # Enhanced handling for 429 (Rate Limit) and 503 (Service Unavailable)
            if response.status_code in (429, 503) and retries < self.MAX_RETRIES:
                # Check for Retry-After header
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = float(retry_after)
                        # Cap Retry-After at 5 minutes to prevent hanging on extended blocks
                        # (Figma sometimes returns huge values for IP/token-level rate limits)
                        max_wait = 300  # 5 minutes
                        if wait_time > max_wait:
                            logger.warning(
                                f"Rate limited with Retry-After: {wait_time}s "
                                f"(capped at {max_wait}s). "
                                f"This may indicate a hard IP/token-level block. "
                                f"Consider using a different Figma token or IP address."
                            )
                            wait_time = max_wait
                        else:
                            logger.warning(
                                f"Rate limited (429/503). Retry-After header: {wait_time}s. "
                                f"Waiting (attempt {retries + 1}/{self.MAX_RETRIES})..."
                            )
                    except (ValueError, TypeError):
                        # Invalid Retry-After value, use exponential backoff instead
                        wait_time = self.RETRY_DELAY * (2**retries)
                        logger.warning(
                            f"Invalid Retry-After header: {retry_after}. "
                            f"Using exponential backoff: {wait_time}s"
                        )
                else:
                    # Use exponential backoff if no Retry-After header
                    wait_time = self.RETRY_DELAY * (2**retries)
                    logger.warning(
                        f"Rate limited (429/503). Retrying in {wait_time}s "
                        f"(attempt {retries + 1}/{self.MAX_RETRIES})..."
                    )

                time.sleep(wait_time)
                return self._make_request(endpoint, params, retries + 1)

            error_msg = f"Figma API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise FigmaAPIError(error_msg) from e

        except requests.exceptions.RequestException as e:
            # Retry on connection errors (including "Response ended prematurely")
            if retries < self.MAX_RETRIES:
                wait_time = self.RETRY_DELAY * (2**retries)
                logger.warning(
                    f"Connection error: {e}. Retrying in {wait_time}s "
                    f"(attempt {retries + 1}/{self.MAX_RETRIES})..."
                )
                time.sleep(wait_time)
                return self._make_request(endpoint, params, retries + 1)

            error_msg = f"Request failed after {self.MAX_RETRIES} retries: {e}"
            logger.error(error_msg)
            raise FigmaAPIError(error_msg) from e

    def get_file_metadata(self, file_key: str) -> Dict:
        """Fetch Figma file metadata.

        Args:
            file_key: Figma file key.

        Returns:
            File metadata dictionary.

        Raises:
            FigmaAPIError: If request fails.
        """
        endpoint = f"/files/{file_key}"
        logger.info(f"Fetching metadata for file: {file_key}")
        return self._make_request(endpoint)

    def extract_ui_elements(self, file_key: str, node_id: Optional[str] = None) -> Dict:
        """Extract structured UI elements from Figma design with screenshot URLs.

        Uses Figma API to get structured data and screenshot URLs for screens.
        Extracts text content, component names, hierarchy, element types, and image URLs.

        Args:
            file_key: Figma file key.
            node_id: Optional specific node ID to extract (if None, extracts full document).

        Returns:
            Dictionary with structured UI elements and screenshot URLs:
            {
                "file_name": str,
                "file_key": str,
                "node_id": str or None,
                "ui_elements": {
                    "id": str,
                    "name": str,
                    "type": str,
                    "text": str or None,
                    "screenshot_url": str or None,  # For FRAME/COMPONENT types
                    "children": [...]
                },
                "screen_screenshots": {
                    "screen_name": "screenshot_url",
                    ...
                }
            }

        Raises:
            FigmaAPIError: If metadata fetch fails.

        Example:
            >>> client.extract_ui_elements("abc123")
            {
                "file_name": "Login Flow",
                "screen_screenshots": {
                    "Login Screen": "https://..."
                },
                "ui_elements": {
                    "name": "Login Screen",
                    "type": "FRAME",
                    "screenshot_url": "https://...",
                    "children": [...]
                }
            }
        """
        logger.info(
            f"Extracting UI elements from file: {file_key}, node: {node_id or 'all'}"
        )

        # Fetch file metadata
        metadata = self.get_file_metadata(file_key)

        # Collect all frame/component IDs for screenshot fetching
        frame_ids = []

        def collect_frame_ids(node: Dict):
            """Collect all FRAME and COMPONENT node IDs."""
            node_type = node.get("type")
            if node_type in ["FRAME", "COMPONENT", "COMPONENT_SET"]:
                frame_ids.append(node.get("id"))

            for child in node.get("children", []):
                collect_frame_ids(child)

        def traverse_node(node: Dict, screenshot_map: Dict[str, str]) -> Dict:
            """Recursively extract UI element info from node tree.

            Args:
                node: Figma node dictionary.
                screenshot_map: Mapping of node_id to screenshot URL.

            Returns:
                Simplified UI element dictionary with screenshot URLs.
            """
            node_id = node.get("id")
            element = {
                "id": node_id,
                "name": node.get("name"),
                "type": node.get("type"),
                "visible": node.get("visible", True),
            }

            # Add screenshot URL for frames and components
            if node_id and node_id in screenshot_map:
                element["screenshot_url"] = screenshot_map[node_id]

            # Extract text content if present
            if "characters" in node:
                element["text"] = node["characters"]

            # Extract children recursively
            children = []
            for child in node.get("children", []):
                # Only include visible elements
                if child.get("visible", True):
                    children.append(traverse_node(child, screenshot_map))

            if children:
                element["children"] = children

            return element

        # Find target node
        if node_id:
            # Search for specific node in document tree
            def find_node(current: Dict, target_id: str) -> Optional[Dict]:
                """Find node by ID in tree."""
                if current.get("id") == target_id:
                    return current
                for child in current.get("children", []):
                    found = find_node(child, target_id)
                    if found:
                        return found
                return None

            target_node = find_node(metadata["document"], node_id)
            if not target_node:
                raise FigmaAPIError(f"Node {node_id} not found in file {file_key}")

            # Collect frame IDs from target node
            collect_frame_ids(target_node)
        else:
            # Collect frame IDs from full document
            collect_frame_ids(metadata["document"])

        # Fetch screenshot URLs for all frames (batch request)
        # This is optional - if it fails, we continue without screenshots
        screenshot_map = {}
        screen_screenshots = {}

        if frame_ids and len(frame_ids) <= 50:  # Limit to avoid API overload
            try:
                logger.info(f"Fetching screenshot URLs for {len(frame_ids)} frames/components...")

                # Use longer timeout for image URL generation (can be slow for many frames)
                endpoint = f"/images/{file_key}"
                params = {
                    "ids": ",".join(frame_ids[:50]),  # Figma API limit
                    "scale": 1.0,  # Lower scale for faster processing
                    "format": "png"
                }

                # Temporarily increase timeout for this request
                original_timeout = self.timeout
                self.timeout = 60  # 60 seconds for image generation

                try:
                    images_data = self._make_request(endpoint, params)
                finally:
                    self.timeout = original_timeout  # Restore original timeout

                if "images" in images_data:
                    screenshot_map = images_data["images"]

                    # Build screen name to URL mapping
                    # Find frames in metadata to get their names
                    def map_screen_names(node: Dict):
                        node_id_val = node.get("id")
                        if node_id_val in screenshot_map and screenshot_map[node_id_val]:
                            screen_name = node.get("name", node_id_val)
                            screen_screenshots[screen_name] = screenshot_map[node_id_val]

                        for child in node.get("children", []):
                            map_screen_names(child)

                    if node_id and target_node:
                        map_screen_names(target_node)
                    else:
                        map_screen_names(metadata["document"])

                    logger.info(f"Successfully fetched {len(screenshot_map)} screenshot URLs")
                else:
                    logger.warning("No screenshot URLs returned from Figma API")
            except Exception as e:
                logger.warning(f"Screenshot fetch failed (non-critical): {e}. Continuing without screenshots.")
        elif len(frame_ids) > 50:
            logger.info(f"Too many frames ({len(frame_ids)}) - skipping screenshot URLs to avoid timeout")

        # Traverse and build UI structure with screenshot URLs
        if node_id and target_node:
            ui_structure = traverse_node(target_node, screenshot_map)
        else:
            ui_structure = traverse_node(metadata["document"], screenshot_map)

        result = {
            "file_name": metadata.get("name", "Unknown"),
            "file_key": file_key,
            "node_id": node_id,
            "ui_elements": ui_structure,
            "screen_screenshots": screen_screenshots,  # New: screen name -> URL mapping
        }

        logger.info(f"Successfully extracted UI elements from {result['file_name']} with {len(screen_screenshots)} screen screenshots")
        return result

    def get_screenshot(self, file_key: str, node_id: str, scale: float = 2.0) -> bytes:
        """Download screenshot for specific node/frame.

        Args:
            file_key: Figma file key.
            node_id: Node ID (e.g., "1:2").
            scale: Image scale (1.0, 2.0, 3.0, 4.0).

        Returns:
            Screenshot image bytes.

        Raises:
            FigmaAPIError: If download fails.
        """
        # Get image URL
        endpoint = f"/images/{file_key}"
        params = {"ids": node_id, "scale": scale, "format": "png"}

        logger.info(
            f"Requesting screenshot for node {node_id} in file {file_key} (scale={scale})"
        )
        data = self._make_request(endpoint, params)

        if "images" not in data or node_id not in data["images"]:
            raise FigmaAPIError(f"No image URL returned for node {node_id}")

        image_url = data["images"][node_id]
        if not image_url:
            raise FigmaAPIError(f"Empty image URL for node {node_id}")

        # Download image
        try:
            logger.info(f"Downloading screenshot from: {image_url}")
            # Use longer timeout for image downloads (2x API timeout)
            response = requests.get(image_url, timeout=self.timeout * 2)
            response.raise_for_status()
            return response.content

        except requests.exceptions.RequestException as e:
            raise FigmaAPIError(f"Failed to download screenshot: {e}") from e

    def import_node(
        self,
        file_key: str,
        node_id: str,
        name: Optional[str] = None,
        scale: float = 2.0,
    ) -> FigmaDesign:
        """Import single Figma node as screenshot.

        Args:
            file_key: Figma file key.
            node_id: Node ID.
            name: Optional custom name for the design.
            scale: Image scale.

        Returns:
            FigmaDesign instance.

        Raises:
            FigmaAPIError: If import fails.
        """
        # Get screenshot
        screenshot_bytes = self.get_screenshot(file_key, node_id, scale)

        # Save to file
        if not name:
            name = f"{file_key}_{node_id.replace(':', '-')}"

        filename = f"figma_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = self.storage_dir / filename

        screenshot_path.write_bytes(screenshot_bytes)
        logger.info(f"Saved screenshot: {screenshot_path}")

        # Create FigmaDesign
        try:
            design = FigmaDesign(
                file_key=file_key,
                node_id=node_id,
                name=name,
                screenshot_path=screenshot_path,
                imported_at=datetime.now(),
            )
            logger.info(f"Successfully imported Figma design: {name}")
            return design

        except ValidationError as e:
            raise FigmaAPIError(f"Design validation failed: {e}") from e

    def batch_import_pages(
        self,
        file_key: str,
        node_ids: List[str],
        scale: float = 2.0,
    ) -> List[FigmaDesign]:
        """Import multiple pages/nodes as screenshots.

        Args:
            file_key: Figma file key.
            node_ids: List of node IDs to import.
            scale: Image scale.

        Returns:
            List of FigmaDesign instances.

        Raises:
            FigmaAPIError: If any import fails (partial failure allowed).
        """
        designs: List[FigmaDesign] = []
        errors: List[tuple[str, Exception]] = []

        for node_id in node_ids:
            try:
                design = self.import_node(file_key, node_id, scale=scale)
                designs.append(design)
                # Small delay to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to import node {node_id}: {e}")
                errors.append((node_id, e))

        if errors:
            error_summary = "; ".join([f"{nid}: {e}" for nid, e in errors])
            logger.warning(
                f"Batch import completed with {len(errors)} errors: {error_summary}"
            )

        logger.info(f"Batch import complete: {len(designs)}/{len(node_ids)} successful")
        return designs

    def import_from_url(self, figma_url: str, scale: float = 2.0) -> FigmaDesign:
        """Import design from Figma URL.

        Args:
            figma_url: Full Figma URL.
            scale: Image scale.

        Returns:
            FigmaDesign instance.

        Raises:
            FigmaAPIError: If import fails or URL has no node ID.
        """
        file_key, node_id = self.parse_figma_url(figma_url)

        if not node_id:
            raise FigmaAPIError(
                "No node-id found in URL. Please provide a URL with ?node-id parameter"
            )

        return self.import_node(file_key, node_id, scale=scale)
