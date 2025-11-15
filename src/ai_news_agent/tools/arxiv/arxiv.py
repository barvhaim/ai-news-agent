"""arXiv Tool for fetching AI research papers."""

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Self

import httpx
from beeai_framework.context import RunContext
from beeai_framework.emitter.emitter import Emitter
from beeai_framework.tools import Tool, ToolError
from beeai_framework.tools.types import JSONToolOutput, ToolRunOptions
from pydantic import BaseModel, Field


class ArxivToolInput(BaseModel):
    """Input schema for arXiv Tool."""

    limit: int = Field(
        description="Maximum number of papers to fetch",
        default=10,
        ge=1,
        le=100,
    )
    query: str | None = Field(
        description="Optional search query. If not provided, fetches recent cs.AI papers",
        default=None,
    )


class ArxivTool(Tool[ArxivToolInput, ToolRunOptions, JSONToolOutput[dict[str, Any]]]):
    """Tool for fetching AI research papers from arXiv."""

    name = "Arxiv"
    description = (
        "Fetches AI research papers from arXiv. Can search by keywords or fetch "
        "recent papers from the cs.AI (Artificial Intelligence) category. "
        "Returns title, authors, abstract, publication date, and links to papers."
    )
    input_schema = ArxivToolInput

    # arXiv API configuration
    BASE_URL = "https://export.arxiv.org/api/query"
    ATOM_NAMESPACE = "{http://www.w3.org/2005/Atom}"
    ARXIV_NAMESPACE = "{http://arxiv.org/schemas/atom}"

    def _create_emitter(self) -> Emitter:
        """Creates event emitter for tool lifecycle events."""
        return Emitter.root().child(
            namespace=["tool", "arxiv"],
            creator=self,
        )

    async def _run(  # pylint: disable=arguments-renamed
        self,
        input_data: ArxivToolInput,
        options: ToolRunOptions | None,
        context: RunContext,
    ) -> JSONToolOutput[dict[str, Any]]:
        """
        Fetch AI papers from arXiv.

        Args:
            input_data: Input parameters including limit and optional query
            options: Tool run options
            context: Run context

        Returns:
            JSONToolOutput containing arXiv papers
        """
        results = await self._fetch_papers(input_data.limit, input_data.query)
        return JSONToolOutput(results)

    async def clone(self) -> Self:
        """Creates a copy of the tool instance for parallel execution."""
        tool = self.__class__(options=self.options)
        tool.name = self.name
        tool.description = self.description
        tool.input_schema = self.input_schema
        tool.middlewares.extend(self.middlewares)
        tool._cache = await self.cache.clone()  # pylint: disable=protected-access
        return tool

    @staticmethod
    def _parse_paper_entry(entry: ET.Element) -> dict[str, Any]:
        """
        Parse a single paper entry from arXiv XML response.

        Args:
            entry: XML entry element

        Returns:
            Dictionary containing paper details
        """
        ns_atom = ArxivTool.ATOM_NAMESPACE
        ns_arxiv = ArxivTool.ARXIV_NAMESPACE

        # Extract basic fields
        paper_id = entry.find(f"{ns_atom}id")
        title = entry.find(f"{ns_atom}title")
        summary = entry.find(f"{ns_atom}summary")
        published = entry.find(f"{ns_atom}published")
        updated = entry.find(f"{ns_atom}updated")

        # Extract authors
        authors = []
        for author in entry.findall(f"{ns_atom}author"):
            name = author.find(f"{ns_atom}name")
            if name is not None and name.text:
                authors.append(name.text.strip())

        # Extract links (PDF and abstract)
        pdf_link = None
        abstract_link = None
        for link in entry.findall(f"{ns_atom}link"):
            if link.get("title") == "pdf":
                pdf_link = link.get("href")
            elif link.get("rel") == "alternate":
                abstract_link = link.get("href")

        # Extract categories
        categories = []
        primary_category = entry.find(f"{ns_arxiv}primary_category")
        if primary_category is not None:
            categories.append(primary_category.get("term", ""))

        for category in entry.findall(f"{ns_atom}category"):
            cat_term = category.get("term")
            if cat_term and cat_term not in categories:
                categories.append(cat_term)

        # Format dates
        published_date = ""
        updated_date = ""
        if published is not None and published.text:
            try:
                published_date = datetime.fromisoformat(
                    published.text.replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                published_date = published.text[:10] if published.text else ""

        if updated is not None and updated.text:
            try:
                updated_date = datetime.fromisoformat(updated.text.replace("Z", "+00:00")).strftime(
                    "%Y-%m-%d"
                )
            except (ValueError, AttributeError):
                updated_date = updated.text[:10] if updated.text else ""

        return {
            "id": paper_id.text.strip() if paper_id is not None and paper_id.text else "",
            "title": title.text.strip() if title is not None and title.text else "",
            "abstract": summary.text.strip() if summary is not None and summary.text else "",
            "authors": authors,
            "published": published_date,
            "updated": updated_date,
            "pdf_link": pdf_link,
            "abstract_link": abstract_link,
            "categories": categories,
        }

    @staticmethod
    async def _fetch_papers(limit: int, query: str | None = None) -> dict[str, Any]:
        """
        Fetch AI papers from arXiv.

        Args:
            limit: Maximum number of papers to return
            query: Optional search query

        Returns:
            Dictionary containing papers and metadata

        Raises:
            ToolError: If API request fails
        """
        proxy = os.environ.get("BEEAI_ARXIV_TOOL_PROXY")

        # Construct search query
        if query:
            # User provided query + cs.AI category filter
            search_query = f"cat:cs.AI AND ({query})"
        else:
            # Just recent cs.AI papers
            search_query = "cat:cs.AI"

        # Build query parameters
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient(proxy=proxy, timeout=30.0) as client:
            try:
                response = await client.get(ArxivTool.BASE_URL, params=params)
                response.raise_for_status()

                # Parse XML response
                root = ET.fromstring(response.content)
                ns_atom = ArxivTool.ATOM_NAMESPACE

                # Extract paper entries
                entries = root.findall(f"{ns_atom}entry")
                papers = []

                for entry in entries:
                    paper = ArxivTool._parse_paper_entry(entry)
                    papers.append(paper)

                return {
                    "papers": papers,
                    "total_fetched": len(papers),
                    "query": query if query else "recent cs.AI papers",
                }

            except httpx.HTTPStatusError as e:
                raise ToolError(
                    f"HTTP error fetching arXiv papers: {e.response.status_code}"
                ) from e
            except httpx.RequestError as e:
                raise ToolError(f"Network error fetching arXiv papers: {str(e)}") from e
            except ET.ParseError as e:
                raise ToolError(f"Error parsing arXiv XML response: {str(e)}") from e
            except Exception as e:
                raise ToolError(f"Unexpected error fetching arXiv papers: {str(e)}") from e
