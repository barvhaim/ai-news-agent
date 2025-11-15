"""Tool for fetching trending AI/ML research papers from Hugging Face Hub."""

import os
from typing import Any, Self

import httpx
from beeai_framework.context import RunContext
from beeai_framework.emitter.emitter import Emitter
from beeai_framework.tools import Tool, ToolError
from beeai_framework.tools.types import JSONToolOutput, ToolRunOptions
from pydantic import BaseModel, Field


class HuggingFacePapersToolInput(BaseModel):
    """Input schema for HuggingFace Papers Tool."""

    limit: int = Field(description="Maximum number of papers to fetch", default=10, ge=1, le=100)


class HuggingFacePapersTool(
    Tool[HuggingFacePapersToolInput, ToolRunOptions, JSONToolOutput[dict[str, Any]]]
):
    """Fetches daily trending papers from Hugging Face Hub with summaries and metrics."""

    name = "HuggingFacePapers"
    description = (
        "Fetch daily trending papers from Hugging Face Hub. "
        "Returns recent AI/ML research papers with titles, summaries, "
        "authors, GitHub links, and community engagement metrics."
    )
    input_schema = HuggingFacePapersToolInput

    def _create_emitter(self) -> Emitter:
        """Creates event emitter for tool lifecycle events"""
        return Emitter.root().child(
            namespace=["tool", "huggingface", "papers"],
            creator=self,
        )

    @staticmethod
    async def _fetch_papers(limit: int) -> dict[str, Any]:
        """Fetch papers from Hugging Face API"""
        url = "https://huggingface.co/api/daily_papers"

        async with httpx.AsyncClient(
            proxy=os.environ.get("BEEAI_HF_PAPERS_TOOL_PROXY"), timeout=30.0
        ) as client:
            try:
                response = await client.get(url, headers={"Accept": "application/json"})
                response.raise_for_status()
                papers_data = response.json()

                # Limit results
                papers_data = papers_data[:limit]

                # Format the response
                formatted_papers = []
                for item in papers_data:
                    paper = item.get("paper", {})
                    formatted_paper = {
                        "id": paper.get("id"),
                        "title": paper.get("title"),
                        "summary": paper.get("ai_summary"),
                        "keywords": paper.get("ai_keywords", []),
                        "authors": [
                            author.get("name")
                            for author in paper.get("authors", [])
                            if not author.get("hidden", False)
                        ],
                        "publishedAt": item.get("publishedAt"),
                        "upvotes": paper.get("upvotes", 0),
                        "numComments": item.get("numComments", 0),
                        "githubRepo": paper.get("githubRepo"),
                        "githubStars": paper.get("githubStars"),
                        "url": (
                            f"https://huggingface.co/papers/{paper.get('id')}"
                            if paper.get("id")
                            else None
                        ),
                    }
                    formatted_papers.append(formatted_paper)

                return {"papers": formatted_papers, "total_fetched": len(formatted_papers)}

            except httpx.HTTPStatusError as e:
                raise ToolError(f"HTTP error fetching papers: {e.response.status_code}") from e
            except httpx.RequestError as e:
                raise ToolError(f"Network error fetching papers: {str(e)}") from e
            except Exception as e:
                raise ToolError(f"Unexpected error fetching papers: {str(e)}") from e

    async def _run(  # pylint: disable=arguments-renamed
        self,
        input_data: HuggingFacePapersToolInput,
        options: ToolRunOptions | None,
        context: RunContext,
    ) -> JSONToolOutput[dict[str, Any]]:
        """Main execution method for the tool"""
        results = await self._fetch_papers(input_data.limit)
        return JSONToolOutput(results)

    async def clone(self) -> Self:
        """Creates a copy of the tool instance"""
        tool = self.__class__(options=self.options)
        tool.name = self.name
        tool.description = self.description
        tool.input_schema = self.input_schema
        tool.middlewares.extend(self.middlewares)
        tool._cache = await self.cache.clone()  # pylint: disable=protected-access
        return tool
