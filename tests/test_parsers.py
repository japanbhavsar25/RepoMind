# tests/test_parsers.py
"""Tests for the AST parser."""

import tempfile
from pathlib import Path

from repomind.parser import PythonExtractor, extract_file, file_hash


def test_extract_simple_function():
    """Test that we can extract a basic function."""
    source = '''
def hello(name):
    """Say hello."""
    return f"Hello, {name}!"
'''
    extractor = PythonExtractor(source)
    funcs = extractor.extract_functions(file_id=1)

    assert len(funcs) == 1
    assert funcs[0].name == "hello"
    assert funcs[0].docstring == "Say hello."


def test_extract_class_with_method():
    """Test that we can extract a class and its methods."""
    source = '''
class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "calc.py"
        path.write_text(source)

        funcs, classes, imports = extract_file(path, file_id=1)

        assert len(classes) == 1
        assert classes[0].name == "Calculator"
        assert classes[0].docstring == "A simple calculator."

        # Should find the method with qualified name
        methods = [f for f in funcs if f.qualified_name == "Calculator.add"]
        assert len(methods) == 1


def test_extract_imports():
    """Test that we can extract import statements."""
    source = '''
import os
from pathlib import Path
from typing import List, Dict
'''
    extractor = PythonExtractor(source)
    imports = extractor.extract_imports(file_id=1)

    assert len(imports) == 4  # os, Path, List, Dict

    # Check first import
    assert imports[0].module_name == "os"
    assert imports[0].is_from_import is False

    # Check from-import
    path_import = [i for i in imports if i.imported_name == "Path"][0]
    assert path_import.module_name == "pathlib"
    assert path_import.is_from_import is True


def test_file_hash_consistency():
    """Test that the same file produces the same hash."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.py"
        path.write_text("print('hello')")

        hash1 = file_hash(path)
        hash2 = file_hash(path)

        assert hash1 == hash2
        assert len(hash1) == 16  # We truncate to 16 chars


def test_extract_nested_and_conditional_functions():
    """Functions inside functions, if-blocks and try-blocks must be found."""
    source = '''
def top_level():
    def nested():
        pass
    return nested

if True:
    def conditional():
        pass

try:
    def in_try():
        pass
except Exception:
    pass
'''
    extractor = PythonExtractor(source)
    names = {f.name for f in extractor.extract_functions(file_id=1)}
    assert names == {"top_level", "nested", "conditional", "in_try"}


def test_qualified_names_track_nesting():
    """Methods of nested classes and nested functions get dotted names."""
    source = '''
class Outer:
    class Inner:
        def method(self):
            pass

    def free_method(self):
        def helper():
            pass
        return helper
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nested.py"
        path.write_text(source)

        funcs, classes, _ = extract_file(path, file_id=1)

    qnames = {f.qualified_name for f in funcs}
    assert "Outer.Inner.method" in qnames
    assert "Outer.free_method" in qnames
    assert "Outer.free_method.helper" in qnames
    assert {c.qualified_name for c in classes} == {"Outer", "Outer.Inner"}


def test_relative_imports_resolve_against_package():
    """'from . import x' in pkg/cli.py resolves to module 'pkg.x'."""
    source = '''
from . import database
from .sub import helper
from ..other import thing
import os
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cli.py"
        path.write_text(source)

        _, _, imports = extract_file(path, file_id=1, rel_path="pkg/cli.py")

    by_name = {i.imported_name: i.module_name for i in imports}
    # 'from . import database': the module is the current package, the
    # binding is the imported name — the graph builder combines them.
    assert by_name["database"] == "pkg"
    assert by_name["helper"] == "pkg.sub"
    # level=2 goes above the top-level package: cannot resolve
    assert by_name["thing"] is None
    assert by_name["os"] == "os"


def test_init_file_resolves_to_package():
    """'from . import utils' in pkg/__init__.py records the package itself."""
    source = "from . import utils\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "__init__.py"
        path.write_text(source)

        _, _, imports = extract_file(path, file_id=1, rel_path="pkg/__init__.py")

    assert imports[0].module_name == "pkg"
    assert imports[0].imported_name == "utils"


def test_extract_file_accepts_preloaded_source():
    """Passing source avoids re-reading the file."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m.py"
        path.write_text("def a():\n    pass\n")

        funcs, _, _ = extract_file(path, file_id=1, source="def b():\n    pass\n")

    assert [f.name for f in funcs] == ["b"]


def test_find_python_files_skips_hidden_dirs_inside_root_only(tmp_path):
    from repomind.utils import find_python_files

    # Root itself lives under hidden and "build" folders, like a clone in .repomind_data/
    root = tmp_path / ".repomind_data" / "build" / "clone"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".backup_old").mkdir()
    (root / ".backup_old" / "stale.py").write_text("y = 2\n", encoding="utf-8")
    (root / "build").mkdir()
    (root / "build" / "gen.py").write_text("z = 3\n", encoding="utf-8")

    found = [p.relative_to(root).as_posix() for p in find_python_files(root)]
    assert found == ["pkg/mod.py"]
