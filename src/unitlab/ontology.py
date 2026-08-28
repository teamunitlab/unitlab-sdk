from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any


class Shape(str, Enum):
    BOUNDING_BOX = "bounding_box"
    POLYGON = "polygon"
    POINT = "point"
    SKELETON = "skeleton"
    POLYLINE = "polyline"
    BITMASK = "bitmask"
    CUBOID = "cuboid"
    TIME_RANGE = "time_range"
    TEXT = "text"
    INTERVAL = "interval"
    INSTANT = "instant"


class OntologyClassificationLevel(str, Enum):
    GLOBAL = "global"


class RadioAttribute:
    value = "radio"


class ChecklistAttribute:
    value = "checklist"


class TextAttribute:
    value = "text"


class NumericAttribute:
    value = "numeric"


class OntologyOption:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    @property
    def title(self) -> str:
        return str(self._data["label"])

    def add_nested_attribute(
        self,
        attribute_type,
        name: str,
        *,
        required: bool = False,
        dynamic: bool = False,
    ) -> OntologyAttribute:
        """Add an attribute shown only when this option is selected.

        Args:
            attribute_type: One of the public attribute marker classes.
            name: User-facing attribute name.
            required: Whether the conditional attribute requires an answer.
            dynamic: Whether its value may change across video keyframes.

        Returns:
            A handle for adding options or deeper conditional attributes.
        """
        attributes = self._data.setdefault("options", [])
        return _add_attribute(
            attributes,
            attribute_type,
            name,
            parent_id=str(self._data["id"]),
            required=required,
            dynamic=dynamic,
        )


class OntologyAttribute:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    @property
    def title(self) -> str:
        return str(self._data["name"])

    @property
    def options(self) -> list[OntologyOption]:
        return [OntologyOption(option) for option in self._data.get("options", [])]

    def add_option(self, label: str) -> OntologyOption:
        if self._data["type"] not in {"radio", "checklist"}:
            raise ValueError(f"{self._data['type']} attributes cannot have options.")
        options = self._data.setdefault("options", [])
        option = {
            "id": f"{self._data['id']}.{len(options) + 1}",
            "label": label,
            "value": label,
        }
        options.append(option)
        return OntologyOption(option)


def _add_attribute(
    attributes: list[dict[str, Any]],
    attribute_type,
    name: str,
    *,
    parent_id: str,
    required: bool,
    dynamic: bool,
) -> OntologyAttribute:
    attribute_type = str(getattr(attribute_type, "value", attribute_type)).lower()
    if attribute_type not in {"radio", "checklist", "text", "numeric"}:
        raise ValueError(f"Unsupported ontology attribute type: {attribute_type}.")
    attribute = {
        "id": f"{parent_id}.{len(attributes) + 1}",
        "name": name,
        "type": attribute_type,
        "required": required,
        "dynamic": dynamic,
        "archived": False,
    }
    attributes.append(attribute)
    return OntologyAttribute(attribute)


class OntologyObject:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    @property
    def title(self) -> str:
        return str(self._data["name"])

    @property
    def shape(self) -> Shape:
        return Shape(self._data["shape"])

    @property
    def attributes(self) -> list[OntologyAttribute]:
        return [
            OntologyAttribute(attribute)
            for attribute in self._data.get("attributes", [])
        ]

    def add_attribute(
        self,
        attribute_type,
        name: str,
        *,
        required: bool = False,
        dynamic: bool = False,
    ) -> OntologyAttribute:
        return _add_attribute(
            self._data.setdefault("attributes", []),
            attribute_type,
            name,
            parent_id=str(self._data["id"]),
            required=required,
            dynamic=dynamic,
        )


class OntologyClassification:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    @property
    def attributes(self) -> list[OntologyAttribute]:
        return [
            OntologyAttribute(attribute)
            for attribute in self._data.get("attributes", [])
        ]

    def add_attribute(
        self,
        attribute_type,
        name: str,
        *,
        required: bool = False,
        dynamic: bool = False,
    ) -> OntologyAttribute:
        return _add_attribute(
            self._data.setdefault("attributes", []),
            attribute_type,
            name,
            parent_id=str(self._data["id"]),
            required=required,
            dynamic=dynamic,
        )


class OntologyStructure:
    def __init__(self, data: dict[str, Any] | None = None):
        self._data = deepcopy(
            data
            or {
                "objects": [],
                "classifications": [],
                "skeleton_templates": [],
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OntologyStructure:
        return cls(data)

    @property
    def objects(self) -> list[OntologyObject]:
        return [OntologyObject(item) for item in self._data.get("objects", [])]

    @property
    def classifications(self) -> list[OntologyClassification]:
        return [
            OntologyClassification(item)
            for item in self._data.get("classifications", [])
        ]

    def add_object(
        self,
        name: str,
        shape: Shape,
        color: str | None = None,
    ) -> OntologyObject:
        """Add a visual annotation class.

        Args:
            name: User-facing class name.
            shape: Geometry used to label the object.
            color: Hex display color; uses the SDK default when omitted.

        Returns:
            A handle for adding object attributes.
        """
        objects = self._data.setdefault("objects", [])
        object_ = {
            "id": str(len(objects) + 1),
            "name": name,
            "color": color or "#D33115",
            "shape": Shape(shape).value,
            "required": False,
            "archived": False,
            "attributes": [],
        }
        objects.append(object_)
        return OntologyObject(object_)

    def add_classification(
        self,
        level: OntologyClassificationLevel | None = None,
    ) -> OntologyClassification:
        """Add a whole-item classification without annotation geometry.

        Args:
            level: Classification scope, such as ``GLOBAL``.

        Returns:
            A handle for adding classification attributes.
        """
        classifications = self._data.setdefault("classifications", [])
        classification = {
            "id": str(len(classifications) + 1),
            "attributes": [],
        }
        if level is not None:
            classification["classification_type"] = OntologyClassificationLevel(
                level
            ).value
        classifications.append(classification)
        return OntologyClassification(classification)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)
