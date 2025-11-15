.PHONY: help install format lint run clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies using uv"
	@echo "  make format     - Format code with black"
	@echo "  make lint       - Run pylint on source code"
	@echo "  make run        - Run the Chainlit application with watch mode"
	@echo "  make clean      - Remove Python cache files"

install:
	uv sync

format:
	uv run black .

lint:
	uv run pylint src/

run:
	uv run chainlit run main.py -w

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
