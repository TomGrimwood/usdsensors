.PHONY: check fmt

check:  ## lint, format, types, the tests: seconds
	@uv run -q python scripts/check.py

fmt:  ## fix what ruff can fix, and format
	@uvx ruff check -q --fix . ; uvx ruff format -q .
