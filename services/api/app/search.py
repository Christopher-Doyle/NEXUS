"""Read-only provider boundary for selected local document search."""

from typing import Protocol

from app.tool_policy import read_workspace_text


class SearchProvider(Protocol):
    def search(self, workspace: str, selected_files: list[str], query: str) -> dict: ...


class LocalTextSearchProvider:
    """Search selected Markdown/text files with the existing secure reader."""

    def search(self, workspace: str, selected_files: list[str], query: str) -> dict:
        matches = []
        for name in selected_files[:5]:
            _, content = read_workspace_text(workspace, name)
            for line_number, line in enumerate(content.splitlines(), start=1):
                if query.casefold() in line.casefold():
                    matches.append({"source": name, "line": line_number, "excerpt": line[:200]})
                    if len(matches) == 20:
                        return {"query": query, "matches": matches, "truncated": True}
        return {"query": query, "matches": matches, "truncated": False}


SEARCH_PROVIDER: SearchProvider = LocalTextSearchProvider()
