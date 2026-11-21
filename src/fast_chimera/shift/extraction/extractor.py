"""Pattern: Facade / Builder. `FingerprintExtractor.extract()` runs the small extractors in order
and assembles the finished Fingerprint. Each step lives in its own module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fast_chimera import __version__
from fast_chimera.core.exceptions import AstParsingError
from fast_chimera.shift.extraction.class_index import ClassIndex
from fast_chimera.shift.extraction.endpoints import EndpointExtractor
from fast_chimera.shift.extraction.middleware import collect_global_middleware
from fast_chimera.shift.extraction.params import ParameterAnalyzer
from fast_chimera.shift.extraction.router_graph import RouterReferences, build_router_graph
from fast_chimera.shift.extraction.router_nodes import find_router_nodes
from fast_chimera.shift.extraction.source_modules import load_source_modules
from fast_chimera.shift.extraction.tables import TableExtractor
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.hashing import compute_content_hash
from fast_chimera.shift.schema import Fingerprint


class FingerprintExtractor:
    def __init__(self, project_root: str | Path) -> None:
        self._root = Path(project_root).resolve()

    def extract(self) -> Fingerprint:
        if not self._root.is_dir():
            raise AstParsingError(f"Project directory does not exist: {self._root}")

        notes = UnresolvedNotes()
        modules = load_source_modules(self._root, notes)
        class_index = ClassIndex(modules)

        # Database side
        tables = TableExtractor(modules, class_index, notes).extract()

        # HTTP side
        nodes = find_router_nodes(modules, notes)
        references = RouterReferences(nodes)
        graph = build_router_graph(modules, nodes, references, notes)
        endpoints = EndpointExtractor(graph, references, ParameterAnalyzer(class_index), notes).extract(modules)
        middleware = collect_global_middleware(modules, graph, references)

        fingerprint = Fingerprint(
            generator=f"fast-chimera {__version__}",
            project=self._root.name,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            tables=sorted(tables, key=lambda table: table.name),
            endpoints=sorted(endpoints, key=lambda endpoint: (endpoint.path, endpoint.method)),
            middleware=middleware,
            unresolved=notes.to_list(),
        )
        fingerprint.content_sha256 = compute_content_hash(fingerprint)
        return fingerprint
