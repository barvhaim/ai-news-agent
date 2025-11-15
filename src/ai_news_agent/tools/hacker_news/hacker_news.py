"""Hacker News Tool for fetching AI/ML related stories."""

import os
from datetime import datetime
from typing import Any, Self

import httpx
from beeai_framework.context import RunContext
from beeai_framework.emitter.emitter import Emitter
from beeai_framework.tools import Tool, ToolError
from beeai_framework.tools.types import JSONToolOutput, ToolRunOptions
from pydantic import BaseModel, Field


class HackerNewsToolInput(BaseModel):
    """Input schema for Hacker News Tool."""

    limit: int = Field(
        description="Maximum number of AI/ML stories to fetch",
        default=10,
        ge=1,
        le=100,
    )


class HackerNewsTool(Tool[HackerNewsToolInput, ToolRunOptions, JSONToolOutput[dict[str, Any]]]):
    """Tool for fetching AI/ML related news from Hacker News."""

    name = "HackerNews"
    description = (
        "Fetches the latest AI and Machine Learning related stories from Hacker News. "
        "Returns top trending AI/ML stories with title, URL, score, author, and description."
    )
    input_schema = HackerNewsToolInput

    # AI/ML related keywords for filtering
    AI_KEYWORDS = [
        "ai",
        "artificial intelligence",
        "ml",
        "machine learning",
        "deep learning",
        "neural network",
        "llm",
        "gpt",
        "transformer",
        "generative",
        "diffusion",
        "pytorch",
        "tensorflow",
        "hugging face",
        "openai",
        "anthropic",
        "claude",
        "chatgpt",
        "stable diffusion",
        "midjourney",
        "langchain",
        "embedding",
        "fine-tuning",
        "reinforcement learning",
        "computer vision",
        "nlp",
        "natural language",
        "rag",
        "retrieval augmented",
    ]

    def _create_emitter(self) -> Emitter:
        """Creates event emitter for tool lifecycle events."""
        return Emitter.root().child(
            namespace=["tool", "hacker_news"],
            creator=self,
        )

    async def _run(
        self,
        input_data: HackerNewsToolInput,
        options: ToolRunOptions | None,
        context: RunContext,
    ) -> JSONToolOutput[dict[str, Any]]:
        """
        Fetch AI/ML related stories from Hacker News.

        Args:
            input_data: Input parameters including limit
            options: Tool run options
            context: Run context

        Returns:
            JSONToolOutput containing filtered AI/ML stories
        """
        results = await self._fetch_ai_stories(input_data.limit)
        return JSONToolOutput(results)

    async def clone(self) -> Self:
        """Creates a copy of the tool instance for parallel execution."""
        tool = self.__class__(options=self.options)
        tool.name = self.name
        tool.description = self.description
        tool.input_schema = self.input_schema
        tool.middlewares.extend(self.middlewares)
        tool._cache = await self.cache.clone()
        return tool

    @staticmethod
    def _is_ai_related(title: str, text: str | None) -> bool:
        """
        Check if a story is AI/ML related based on title and text.

        Args:
            title: Story title
            text: Story text/description (optional)

        Returns:
            True if story contains AI/ML keywords
        """
        content = f"{title} {text or ''}".lower()
        return any(keyword in content for keyword in HackerNewsTool.AI_KEYWORDS)

    @staticmethod
    async def _fetch_story_details(
        client: httpx.AsyncClient, story_id: int
    ) -> dict[str, Any] | None:
        """
        Fetch details for a single story.

        Args:
            client: HTTP client
            story_id: Story ID to fetch

        Returns:
            Story details or None if fetch fails
        """
        try:
            response = await client.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None

    @staticmethod
    async def _fetch_ai_stories(limit: int) -> dict[str, Any]:
        """
        Fetch AI/ML related top stories from Hacker News.

        Args:
            limit: Maximum number of stories to return

        Returns:
            Dictionary containing filtered stories and metadata

        Raises:
            ToolError: If API request fails
        """
        base_url = "https://hacker-news.firebaseio.com/v0"
        proxy = os.environ.get("BEEAI_HN_TOOL_PROXY")

        async with httpx.AsyncClient(proxy=proxy, timeout=30.0) as client:
            try:
                # Fetch top story IDs
                response = await client.get(f"{base_url}/topstories.json")
                response.raise_for_status()
                story_ids = response.json()

                # Fetch and filter stories
                ai_stories = []
                checked_count = 0
                max_to_check = min(200, len(story_ids))  # Check up to 200 stories

                for story_id in story_ids[:max_to_check]:
                    if len(ai_stories) >= limit:
                        break

                    checked_count += 1
                    story = await HackerNewsTool._fetch_story_details(client, story_id)

                    if not story or story.get("type") != "story":
                        continue

                    title = story.get("title", "")
                    text = story.get("text", "")

                    # Filter for AI/ML content
                    if HackerNewsTool._is_ai_related(title, text):
                        # Format timestamp
                        timestamp = story.get("time", 0)
                        formatted_time = datetime.fromtimestamp(timestamp).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        formatted_story = {
                            "id": story.get("id"),
                            "title": title,
                            "url": story.get(
                                "url", f"https://news.ycombinator.com/item?id={story_id}"
                            ),
                            "score": story.get("score", 0),
                            "author": story.get("by", "unknown"),
                            "time": formatted_time,
                            "text": text if text else None,
                            "comments_count": story.get("descendants", 0),
                        }
                        ai_stories.append(formatted_story)

                # Sort by score (descending)
                ai_stories.sort(key=lambda x: x["score"], reverse=True)

                return {
                    "stories": ai_stories,
                    "total_fetched": len(ai_stories),
                    "total_checked": checked_count,
                }

            except httpx.HTTPStatusError as e:
                raise ToolError(
                    f"HTTP error fetching Hacker News stories: {e.response.status_code}"
                ) from e
            except httpx.RequestError as e:
                raise ToolError(f"Network error fetching Hacker News stories: {str(e)}") from e
            except Exception as e:
                raise ToolError(f"Unexpected error fetching Hacker News stories: {str(e)}") from e
