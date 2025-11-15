# AI-News Agent

An AI-powered assistant for discovering the latest AI/ML news from multiple sources: research papers, interactive demos, tech stories, and academic publications.

![AI-News Agent Interface](public/main.png)

## Quick Start

### Installation
```bash
make install
```

### Run
```bash
make run
```

Or using uv directly:
```bash
uv run chainlit run main.py -w
```

### Environment Setup
Copy `.env.example` to `.env` and configure:
```bash
LLM_MODEL_NAME=ollama:llama3.1  # or openai:gpt-4
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
```

## Features

- **Hugging Face Papers** - Daily trending AI/ML research with AI-generated summaries, keywords, and GitHub links
- **Hugging Face Spaces** - Interactive demos and applications from the community
- **Hacker News** - Latest AI/ML tech stories filtered from top Hacker News posts
- **arXiv Papers** - Search or browse recent AI research from arXiv's cs.AI category
- **Smart Reasoning** - Powered by BeeAI Framework's ReActAgent architecture

![Example Usage](public/example.png)

## Development

```bash
make format    # Format code with Black
make lint      # Run Pylint
make clean     # Remove cache files
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.