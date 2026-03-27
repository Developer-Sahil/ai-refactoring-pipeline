"""
cast.parsers.tree_sitter_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A robust AST-based parser using tree-sitter.
Replaces BraceLanguageParser with guaranteed syntactical accuracy.
"""

from __future__ import annotations

from typing import Optional

import tree_sitter
from cast.chunk_model import CodeChunk
from cast.file_reader import SourceFile
from cast.parsers.base_parser import BaseParser

LANGUAGE_MAP = {}

# We attempt to load the C-bindings for each grammar. If tree-sitter or a specific
# language binding is unavailable (e.g. no C compiler), it safely skips registration
# and the registry fallback logic will utilize BraceLanguageParser.

try:
    import tree_sitter_javascript
    LANGUAGE_MAP["javascript"] = (tree_sitter_javascript.language(), {
        "class": ["class_declaration"],
        "function": ["function_declaration", "generator_function_declaration", "lexical_declaration"],
        "method": ["method_definition"]
    })
except ImportError:
    pass

try:
    import tree_sitter_typescript
    LANGUAGE_MAP["typescript"] = (tree_sitter_typescript.language_typescript(), {
        "class": ["class_declaration", "abstract_class_declaration"],
        "interface": ["interface_declaration"],
        "type_alias": ["type_alias_declaration"],
        "function": ["function_declaration", "generator_function_declaration", "lexical_declaration"],
        "method": ["method_definition", "public_field_definition"]
    })
except ImportError:
    pass

try:
    import tree_sitter_java
    LANGUAGE_MAP["java"] = (tree_sitter_java.language(), {
        "class": ["class_declaration"],
        "interface": ["interface_declaration"],
        "enum": ["enum_declaration"],
        "constructor": ["constructor_declaration"],
        "method": ["method_declaration"]
    })
except ImportError:
    pass

try:
    import tree_sitter_c
    LANGUAGE_MAP["c"] = (tree_sitter_c.language(), {
        "struct": ["struct_specifier"],
        "function": ["function_definition"]
    })
except ImportError:
    pass

try:
    import tree_sitter_cpp
    LANGUAGE_MAP["cpp"] = (tree_sitter_cpp.language(), {
        "struct": ["struct_specifier"],
        "class": ["class_specifier"],
        "namespace": ["namespace_definition"],
        "function": ["function_definition"]
    })
except ImportError:
    pass

try:
    import tree_sitter_go
    LANGUAGE_MAP["go"] = (tree_sitter_go.language(), {
        "struct": ["type_declaration"],
        "interface": ["type_declaration"],
        "function": ["function_declaration", "method_declaration"]
    })
except ImportError:
    pass

try:
    import tree_sitter_rust
    LANGUAGE_MAP["rust"] = (tree_sitter_rust.language(), {
        "function": ["function_item"],
        "struct": ["struct_item"],
        "impl": ["impl_item"],
        "trait": ["trait_item"],
        "enum": ["enum_item"]
    })
except ImportError:
    pass

try:
    import tree_sitter_ruby
    LANGUAGE_MAP["ruby"] = (tree_sitter_ruby.language(), {
        "method": ["method", "singleton_method"],
        "class": ["class"],
        "module": ["module"]
    })
except ImportError:
    pass

try:
    import tree_sitter_php
    LANGUAGE_MAP["php"] = (tree_sitter_php.language_php(), {
        "function": ["function_definition"],
        "method": ["method_declaration"],
        "class": ["class_declaration"],
        "interface": ["interface_declaration"],
        "trait": ["trait_declaration"]
    })
except ImportError:
    pass


class TreeSitterParser(BaseParser):
    def __init__(self, language: str) -> None:
        if language not in LANGUAGE_MAP:
            raise ValueError(f"Tree-sitter not configured or missing bindings for '{language}'")
        
        self.language = language
        language_grammar, node_mappings = LANGUAGE_MAP[language]
        
        self._ts_language = tree_sitter.Language(language_grammar)
        self._parser = tree_sitter.Parser(self._ts_language)
        
        self._target_nodes: dict[str, str] = {}
        for chunk_type, node_types in node_mappings.items():
            for node_type in node_types:
                self._target_nodes[node_type] = chunk_type

    def extract_chunks(self, source: SourceFile) -> list[CodeChunk]:
        tree = self._parser.parse(source.content.encode("utf-8"))
        
        chunks: list[CodeChunk] = []
        self._counter = 1
        
        self._walk_tree(tree.root_node, source, chunks)
        
        chunks.sort(key=lambda c: c.start_line)
        for i, chunk in enumerate(chunks, start=1):
            chunk.chunk_id = self.make_chunk_id(i)
            
        return chunks

    def _walk_tree(self, node: tree_sitter.Node, source: SourceFile, chunks: list[CodeChunk]) -> None:
        if node.type in self._target_nodes:
            chunk_type = self._target_nodes[node.type]
            
            if self.language == "go" and node.type == "type_declaration":
                struct_or_interface = self._find_go_type_kind(node)
                if struct_or_interface:
                    chunk_type = struct_or_interface
                else:
                    return
                    
            if node.type == "lexical_declaration":
                if not self._is_js_arrow_function(node):
                    return

            name = self._extract_identifier(node)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            code = self.slice_lines(source.lines, start_line, end_line)
            
            chunk = CodeChunk(
                chunk_id="", 
                type=chunk_type,
                name=name,
                start_line=start_line,
                end_line=end_line,
                code=code
            )
            chunks.append(chunk)

        for child in node.children:
            self._walk_tree(child, source, chunks)

    def _extract_identifier(self, node: tree_sitter.Node) -> Optional[str]:
        for child in node.children:
            if child.type in ["identifier", "name", "type_identifier", "property_identifier"]:
                return child.text.decode('utf-8') if child.text else None
                
            if child.type in ["function_declarator", "pointer_declarator"]:
                return self._extract_identifier(child)
                
            if child.type == "variable_declarator":
                return self._extract_identifier(child)
                
            if child.type == "field_identifier":
                return child.text.decode('utf-8') if child.text else None
                
            if child.type == "type_spec":
                return self._extract_identifier(child)
                
        # Ruby/PHP specific identifiers usually are direct named children
        # In ruby, the node "name" field or child often stores the method name natively via child_by_field_name
        name_node = node.child_by_field_name('name')
        if name_node and name_node.text:
            return name_node.text.decode('utf-8')

        return None

    def _is_js_arrow_function(self, node: tree_sitter.Node) -> bool:
        for child in node.children:
            if child.type == "variable_declarator":
                for subchild in child.children:
                    if subchild.type in ["arrow_function", "function"]:
                        return True
        return False
        
    def _find_go_type_kind(self, node: tree_sitter.Node) -> Optional[str]:
        for child in node.children:
            if child.type == "type_spec":
                for subchild in child.children:
                    if subchild.type == "struct_type":
                        return "struct"
                    if subchild.type == "interface_type":
                        return "interface"
        return None
