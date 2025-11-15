import os
from typing import Any, Self

import httpx
from beeai_framework.context import RunContext
from beeai_framework.emitter.emitter import Emitter
from beeai_framework.tools import Tool, ToolError
from beeai_framework.tools.types import JSONToolOutput, ToolRunOptions
from pydantic import BaseModel, Field


class HuggingFaceSpacesToolInput(BaseModel):
    limit: int = Field(
        description="Maximum number of trending spaces to fetch",
        default=10,
        ge=1,
        le=100
    )


class HuggingFaceSpacesTool(Tool[HuggingFaceSpacesToolInput, ToolRunOptions, JSONToolOutput[dict[str, Any]]]):
    name = "HuggingFaceSpaces"
    description = "Fetch trending spaces from Hugging Face Hub. Returns popular AI/ML demo applications and interactive tools sorted by trending score, including SDK type, likes, and tags."
    input_schema = HuggingFaceSpacesToolInput

    def __init__(self, options: dict[str, Any] | None = None):
        super().__init__(options)

    def _create_emitter(self) -> Emitter:
        """Creates event emitter for tool lifecycle events"""
        return Emitter.root().child(
            namespace=["tool", "huggingface", "spaces"],
            creator=self,
        )

    @staticmethod
    async def _fetch_spaces(limit: int) -> dict[str, Any]:
        """Fetch trending spaces from Hugging Face API"""
        url = "https://huggingface.co/api/spaces"

        async with httpx.AsyncClient(
            proxy=os.environ.get("BEEAI_HF_SPACES_TOOL_PROXY"),
            timeout=30.0
        ) as client:
            try:
                response = await client.get(
                    url,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                spaces_data = response.json()

                # Sort by trending score (descending)
                spaces_data.sort(
                    key=lambda x: x.get("trendingScore", 0),
                    reverse=True
                )

                # Limit results
                spaces_data = spaces_data[:limit]

                # Format the response
                formatted_spaces = []
                for space in spaces_data:
                    formatted_space = {
                        "id": space.get("id"),
                        "sdk": space.get("sdk"),
                        "likes": space.get("likes", 0),
                        "trendingScore": space.get("trendingScore", 0),
                        "tags": space.get("tags", []),
                        "private": space.get("private", False),
                        "createdAt": space.get("createdAt"),
                        "url": f"https://huggingface.co/spaces/{space.get('id')}" if space.get("id") else None
                    }
                    formatted_spaces.append(formatted_space)

                return {
                    "spaces": formatted_spaces,
                    "total_fetched": len(formatted_spaces)
                }

            except httpx.HTTPStatusError as e:
                raise ToolError(f"HTTP error fetching spaces: {e.response.status_code}") from e
            except httpx.RequestError as e:
                raise ToolError(f"Network error fetching spaces: {str(e)}") from e
            except Exception as e:
                raise ToolError(f"Unexpected error fetching spaces: {str(e)}") from e

    async def _run(
        self,
        input: HuggingFaceSpacesToolInput,
        options: ToolRunOptions | None,
        context: RunContext
    ) -> JSONToolOutput[dict[str, Any]]:
        """Main execution method for the tool"""
        results = await self._fetch_spaces(input.limit)
        return JSONToolOutput(results)

    async def clone(self) -> Self:
        """Creates a copy of the tool instance"""
        tool = self.__class__(options=self.options)
        tool.name = self.name
        tool.description = self.description
        tool.input_schema = self.input_schema
        tool.middlewares.extend(self.middlewares)
        tool._cache = await self.cache.clone()
        return tool
