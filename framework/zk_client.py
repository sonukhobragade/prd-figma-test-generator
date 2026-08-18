#!/usr/bin/env python3
"""
ZK-Web Client for fetching ZooKeeper configurations.

This module connects to ZK-Web (a web UI for ZooKeeper) and fetches
configuration data by parsing HTML responses.

Usage:
    client = ZKWebClient(
        base_url="https://zkweb.example.com",
        username="user",
        password="pass",
        zk_address="zk-host:2181"
    )

    # Get single node
    node = await client.get_node("/myapp/payments/IN/serviceConfig")

    # Walk entire tree
    configs = await client.walk_tree("/myapp", max_depth=5)
"""

import asyncio
import re
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Patterns for sensitive config keys (will be filtered out)
SENSITIVE_PATTERNS = [
    r".*password.*",
    r".*secret.*",
    r".*token.*",
    r".*apikey.*",
    r".*api_key.*",
    r".*credential.*",
    r".*private.*key.*",
    r".*connectionstring.*",
    r".*connection_string.*",
]


@dataclass
class ZKNode:
    """Represents a ZooKeeper node."""

    path: str
    data: Optional[str] = None
    data_length: int = 0
    version: int = 0
    num_children: int = 0
    children: List[str] = field(default_factory=list)
    ctime: Optional[int] = None
    mtime: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "data": self.data,
            "data_length": self.data_length,
            "version": self.version,
            "num_children": self.num_children,
            "children": self.children,
            "ctime": self.ctime,
            "mtime": self.mtime,
        }


class ZKWebClient:
    """
    Client for ZK-Web (ZooKeeper web UI).

    Fetches ZK nodes by parsing HTML responses from ZK-Web.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        zk_address: str,
        timeout: float = 30.0,
        sensitive_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize ZK-Web client.

        Args:
            base_url: ZK-Web base URL (e.g., https://zkweb.example.com)
            username: Basic auth username
            password: Basic auth password
            zk_address: ZooKeeper address (e.g., zk-host:2181)
            timeout: Request timeout in seconds
            sensitive_patterns: Regex patterns for sensitive config keys to filter
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.zk_address = zk_address
        self.timeout = timeout
        self.sensitive_patterns = sensitive_patterns or SENSITIVE_PATTERNS

        # Compile sensitive patterns
        self._sensitive_regex = [
            re.compile(p, re.IGNORECASE) for p in self.sensitive_patterns
        ]

        # HTTP client with auth
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self.username, self.password),
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def _init_session(self) -> bool:
        """
        Initialize session by connecting to ZK.

        ZK-Web requires an /init request to establish ZK connection.
        """
        if self._initialized:
            return True

        try:
            client = await self._get_client()
            url = f"{self.base_url}/init?addr={self.zk_address}"
            response = await client.get(url)

            if response.status_code == 200:
                self._initialized = True
                logger.info(f"ZK-Web session initialized for {self.zk_address}")
                return True
            else:
                logger.error(f"Failed to init ZK-Web: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"ZK-Web init error: {e}")
            return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False

    async def get_node(self, path: str) -> Optional[ZKNode]:
        """
        Fetch a single ZK node.

        Args:
            path: ZK path (e.g., /myapp/payments/IN/serviceConfig)

        Returns:
            ZKNode with data and children, or None if failed
        """
        if not await self._init_session():
            return None

        try:
            client = await self._get_client()
            url = f"{self.base_url}/node?path={path}"
            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch {path}: {response.status_code}")
                return None

            return self._parse_node_html(path, response.text)

        except Exception as e:
            logger.error(f"Error fetching {path}: {e}")
            return None

    def _parse_node_html(self, path: str, html: str) -> ZKNode:
        """
        Parse ZK-Web HTML response to extract node data.

        Args:
            path: The ZK path
            html: HTML response from ZK-Web

        Returns:
            Parsed ZKNode
        """
        soup = BeautifulSoup(html, "html.parser")
        node = ZKNode(path=path)

        # Parse children (links in nav-tabs-stacked)
        children_ul = soup.find("ul", class_="nav-tabs")
        if children_ul:
            for link in children_ul.find_all("a", href=True):
                href = link.get("href", "")
                if href.startswith("/node?path="):
                    child_path = href.replace("/node?path=", "")
                    # Only add direct children
                    if child_path.startswith(path) and child_path != path:
                        child_name = child_path.rstrip("/").split("/")[-1]
                        if child_name:
                            node.children.append(child_name)

        # Parse node stats (table rows)
        stat_table = soup.find("table", class_="table-striped")
        if stat_table:
            for row in stat_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)

                    if key == "numChildren":
                        node.num_children = int(value)
                    elif key == "dataLength":
                        node.data_length = int(value)
                    elif key == "version":
                        node.version = int(value)
                    elif key == "ctime":
                        node.ctime = int(value) if value != "0" else None
                    elif key == "mtime":
                        node.mtime = int(value) if value != "0" else None

        # Parse node data (content in well div)
        data_well = soup.find("div", class_="well")
        if data_well:
            # Get the text, preserving structure
            data_p = data_well.find("p")
            if data_p:
                # Replace <br> with newlines
                for br in data_p.find_all("br"):
                    br.replace_with("\n")
                node.data = data_p.get_text()

                # Clean up the data
                if node.data:
                    node.data = node.data.strip()
                    if not node.data:
                        node.data = None

        return node

    async def walk_tree(
        self,
        root: str,
        max_depth: int = 10,
        filter_sensitive: bool = True,
    ) -> Dict[str, ZKNode]:
        """
        Recursively walk ZK tree and fetch all nodes.

        Args:
            root: Root path to start from (e.g., /myapp)
            max_depth: Maximum depth to traverse
            filter_sensitive: Whether to filter out sensitive config nodes

        Returns:
            Dictionary mapping paths to ZKNode objects
        """
        results: Dict[str, ZKNode] = {}

        async def _walk(path: str, depth: int):
            if depth > max_depth:
                logger.debug(f"Max depth reached at {path}")
                return

            # Check if path should be filtered
            if filter_sensitive and self._is_sensitive_path(path):
                logger.debug(f"Skipping sensitive path: {path}")
                return

            node = await self.get_node(path)
            if not node:
                return

            # Store node if it has data
            if node.data or node.data_length > 0:
                results[path] = node

            # Recursively fetch children
            for child in node.children:
                child_path = f"{path.rstrip('/')}/{child}"
                await _walk(child_path, depth + 1)

        await _walk(root, 0)
        return results

    def _is_sensitive_path(self, path: str) -> bool:
        """Check if path matches sensitive patterns."""
        path_lower = path.lower()
        for regex in self._sensitive_regex:
            if regex.search(path_lower):
                return True
        return False

    async def get_all_configs(
        self,
        paths: List[str],
        max_depth: int = 10,
        filter_sensitive: bool = True,
    ) -> Dict[str, ZKNode]:
        """
        Fetch configs from multiple root paths.

        Args:
            paths: List of root paths to fetch
            max_depth: Maximum depth per path
            filter_sensitive: Whether to filter sensitive configs

        Returns:
            Combined dictionary of all configs
        """
        all_configs: Dict[str, ZKNode] = {}

        for path in paths:
            logger.info(f"Fetching configs from {path}...")
            configs = await self.walk_tree(path, max_depth, filter_sensitive)
            all_configs.update(configs)
            logger.info(f"  Found {len(configs)} configs under {path}")

        return all_configs


def format_configs_for_indexing(configs: Dict[str, ZKNode]) -> List[Dict[str, Any]]:
    """
    Format ZK configs for RAG indexing.

    Args:
        configs: Dictionary of path -> ZKNode

    Returns:
        List of documents ready for indexing
    """
    documents = []

    for path, node in configs.items():
        if not node.data:
            continue

        # Extract config category from path
        # /myapp/payments/IN/serviceConfig -> payments
        parts = path.strip("/").split("/")
        category = parts[1] if len(parts) > 1 else "root"

        # Extract config name from path
        config_name = parts[-1] if parts else path

        # Format document text
        doc_text = f"""
ZK Config: {config_name}
Path: {path}
Category: {category}
Version: {node.version}

Data:
{node.data}
""".strip()

        documents.append({
            "text": doc_text,
            "metadata": {
                "doc_type": "zk_live",
                "path": path,
                "config_name": config_name,
                "category": category,
                "version": node.version,
                "data_length": node.data_length,
                "mtime": node.mtime,
                "fetched_at": datetime.now().isoformat(),
            }
        })

    return documents


# Convenience function for quick testing
async def test_connection(
    base_url: str,
    username: str,
    password: str,
    zk_address: str,
    test_path: str = "/",
) -> bool:
    """
    Test ZK-Web connection.

    Args:
        base_url: ZK-Web URL
        username: Auth username
        password: Auth password
        zk_address: ZK address
        test_path: Path to test fetch

    Returns:
        True if connection successful
    """
    client = ZKWebClient(
        base_url=base_url,
        username=username,
        password=password,
        zk_address=zk_address,
    )

    try:
        node = await client.get_node(test_path)
        if node:
            print("✓ Connected to ZK-Web")
            print(f"  Root has {node.num_children} children")
            return True
        else:
            print("✗ Failed to fetch root node")
            return False
    finally:
        await client.close()


if __name__ == "__main__":
    # Quick test
    import os
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(test_connection(
        base_url=os.getenv("ZK_NAVIGATOR_URL", ""),
        username=os.getenv("ZK_NAVIGATOR_USER", ""),
        password=os.getenv("ZK_NAVIGATOR_PASS", ""),
        zk_address=os.getenv("ZK_ADDRESS", ""),
    ))
