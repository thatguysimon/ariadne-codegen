from typing import Any, Dict, List, Optional, Set, Tuple, Union

from graphql import (
    ArgumentNode,
    FieldNode,
    InlineFragmentNode,
    NamedTypeNode,
    NameNode,
    SelectionSetNode,
    VariableNode,
)


class GraphQLArgument:
    def __init__(self, argument_name: str, argument_value: Any):
        self._name = argument_name
        self._value = argument_value

    def to_ast(self) -> ArgumentNode:
        return ArgumentNode(
            name=NameNode(value=self._name),
            value=VariableNode(name=NameNode(value=self._value)),
        )


class GraphQLField:
    def __init__(
        self, field_name: str, arguments: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        self._field_name = field_name
        self._variables = arguments or {}
        self._formatted_variables: Dict[str, Dict[str, Any]] = {}
        self._subfields: List[GraphQLField] = []
        self._alias: Optional[str] = None
        self._inline_fragments: Dict[str, Tuple[GraphQLField, ...]] = {}

    def alias(self, alias: str) -> "GraphQLField":
        self._alias = alias
        return self

    def add_subfield(self, subfield: "GraphQLField") -> None:
        self._subfields.append(subfield)

    def add_inline_fragment(self, type_name: str, *subfields: "GraphQLField") -> None:
        self._inline_fragments[type_name] = subfields

    def _build_field_name(self) -> str:
        return f"{self._alias}: {self._field_name}" if self._alias else self._field_name

    def _build_selections(
        self, idx: int, used_names: Set[str]
    ) -> List[Union[FieldNode, InlineFragmentNode]]:
        selections: List[Union[FieldNode, InlineFragmentNode]] = [
            subfield.to_ast(idx, used_names) for subfield in self._subfields
        ]
        for name, subfields in self._inline_fragments.items():
            selections.append(
                InlineFragmentNode(
                    type_condition=NamedTypeNode(name=NameNode(value=name)),
                    selection_set=SelectionSetNode(
                        selections=[
                            subfield.to_ast(idx, used_names) for subfield in subfields
                        ]
                    ),
                )
            )
        return selections

    def _format_variable_name(
        self, idx: int, var_name: str, used_names: Set[str]
    ) -> str:
        base_name = f"{idx}_{var_name}"
        unique_name = base_name
        counter = 1
        while unique_name in used_names:
            unique_name = f"{base_name}_{counter}"
            counter += 1
        used_names.add(unique_name)
        return unique_name

    def _collect_all_variables(self, idx: int, used_names: Set[str]) -> None:
        self._formatted_variables = {}
        for k, v in self._variables.items():
            unique_name = self._format_variable_name(idx, k, used_names)
            self._formatted_variables[unique_name] = {
                "name": k,
                "type": v["type"],
                "value": v["value"],
            }

    def to_ast(self, idx: int, used_names: Optional[Set[str]] = None) -> FieldNode:
        if used_names is None:
            used_names = set()
        self._collect_all_variables(idx, used_names)
        formatted_args = [
            GraphQLArgument(v["name"], k).to_ast()
            for k, v in self._formatted_variables.items()
        ]
        return FieldNode(
            name=NameNode(value=self._build_field_name()),
            arguments=formatted_args,
            selection_set=(
                SelectionSetNode(selections=self._build_selections(idx, used_names))
                if self._subfields or self._inline_fragments
                else None
            ),
        )

    def get_formatted_variables(self) -> Dict[str, Dict[str, Any]]:
        formatted_variables = self._formatted_variables
        for subfield in self._subfields:
            subfield.get_formatted_variables()
            self._formatted_variables.update(subfield._formatted_variables)
        for subfields in self._inline_fragments.values():
            for subfield in subfields:
                subfield.get_formatted_variables()
                self._formatted_variables.update(subfield._formatted_variables)
        return formatted_variables
