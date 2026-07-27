from __future__ import annotations

import itertools
import re
import string
from typing import Any


def tiles_from_template(
    template: str,
    tile_values: dict[str, list[str]],
) -> dict[str, Any]:
    """Compile a filename template into a Data Group configuration.

    Fields present in ``tile_values`` identify tiles; the remaining template
    fields identify the group shared by those tiles.

    Args:
        template: Literal filename pattern, such as ``"{patient_id}_{view}"``.
        tile_values: Allowed values for each tile-discriminating field.

    Returns:
        A configuration accepted by folder grouping methods.

    Raises:
        ValueError: If no tile values are supplied, a field is unknown, or the
            template has no remaining grouping field.
    """
    if not tile_values:
        raise ValueError("tile_values must define at least one tile discriminator.")
    parsed = list(string.Formatter().parse(template))
    fields = [field for _, field, _, _ in parsed if field]
    unknown = set(tile_values) - set(fields)
    if unknown:
        raise ValueError(f"Unknown template fields: {', '.join(sorted(unknown))}")
    grouping_keys = [field for field in fields if field not in tile_values]
    if not grouping_keys:
        raise ValueError("Template needs at least one grouping field.")

    discriminator_names = list(tile_values)
    combinations = itertools.product(
        *(tile_values[name] for name in discriminator_names)
    )
    tiles = []
    for combination in combinations:
        values = dict(zip(discriminator_names, combination, strict=True))
        body = ""
        for literal, field, _format_spec, _conversion in parsed:
            body += re.escape(literal)
            if not field:
                continue
            if field in grouping_keys:
                body += f"(?P<{field}>.+?)"
            else:
                body += re.escape(str(values[field]))
        title = " / ".join(str(values[name]) for name in discriminator_names)
        tile_id = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "tile"
        tile = {
            "tile_id": tile_id,
            "title": title,
            "match_rule": f"^{body}(?:\\..*)?$",
            "exclusions": [],
        }
        tiles.append(tile)

    return {
        "grouping_keys": grouping_keys,
        "group_name_template": " ".join(f"{{{key}}}" for key in grouping_keys),
        "tiles": tiles,
        "minimum_matched_tiles": 1,
        "required_tiles": [],
        "incomplete_group_handling": "allow_incomplete",
        "layout_type": "grid",
        "recursive": True,
    }
