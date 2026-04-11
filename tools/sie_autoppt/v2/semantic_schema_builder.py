from __future__ import annotations

import copy
from typing import Any

from .schema import SUPPORTED_THEMES


SUPPORTED_SLIDE_INTENTS = (
    "cover",
    "section",
    "narrative",
    "comparison",
    "framework",
    "analysis",
    "summary",
    "conclusion",
)

BLOCK_KIND_SCHEMAS: dict[str, dict[str, Any]] = {
    "bullets": {
        "type": "object",
        "properties": {
            "kind": {"const": "bullets"},
            "heading": {"type": "string", "maxLength": 24},
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {"type": "string", "minLength": 2, "maxLength": 70},
            },
        },
        "required": ["kind", "items"],
        "additionalProperties": False,
    },
    "comparison": {
        "type": "object",
        "properties": {
            "kind": {"const": "comparison"},
            "left_heading": {"type": "string", "minLength": 1, "maxLength": 24},
            "left_items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string", "minLength": 2, "maxLength": 60},
            },
            "right_heading": {"type": "string", "minLength": 1, "maxLength": 24},
            "right_items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string", "minLength": 2, "maxLength": 60},
            },
        },
        "required": ["kind", "left_heading", "left_items", "right_heading", "right_items"],
        "additionalProperties": False,
    },
    "image": {
        "type": "object",
        "properties": {
            "kind": {"const": "image"},
            "mode": {"type": "string", "enum": ["placeholder", "local_path"]},
            "caption": {"type": "string", "maxLength": 40},
            "path": {"type": "string", "maxLength": 240},
        },
        "required": ["kind", "mode"],
        "additionalProperties": False,
    },
    "statement": {
        "type": "object",
        "properties": {
            "kind": {"const": "statement"},
            "text": {"type": "string", "minLength": 2, "maxLength": 100},
        },
        "required": ["kind", "text"],
        "additionalProperties": False,
    },
    "timeline": {
        "type": "object",
        "properties": {
            "kind": {"const": "timeline"},
            "heading": {"type": "string", "maxLength": 24},
            "stages": {
                "type": "array",
                "minItems": 2,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 24},
                        "detail": {"type": "string", "maxLength": 60},
                    },
                    "required": ["title"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["kind", "stages"],
        "additionalProperties": False,
    },
    "cards": {
        "type": "object",
        "properties": {
            "kind": {"const": "cards"},
            "heading": {"type": "string", "maxLength": 24},
            "cards": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 24},
                        "body": {"type": "string", "maxLength": 60},
                    },
                    "required": ["title"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["kind", "cards"],
        "additionalProperties": False,
    },
    "stats": {
        "type": "object",
        "properties": {
            "kind": {"const": "stats"},
            "heading": {"type": "string", "maxLength": 24},
            "metrics": {
                "type": "array",
                "minItems": 2,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "minLength": 1, "maxLength": 24},
                        "value": {"type": "string", "minLength": 1, "maxLength": 24},
                        "note": {"type": "string", "maxLength": 40},
                    },
                    "required": ["label", "value"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["kind", "metrics"],
        "additionalProperties": False,
    },
    "matrix": {
        "type": "object",
        "properties": {
            "kind": {"const": "matrix"},
            "heading": {"type": "string", "maxLength": 24},
            "x_axis": {"type": "string", "maxLength": 24},
            "y_axis": {"type": "string", "maxLength": 24},
            "cells": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 24},
                        "body": {"type": "string", "maxLength": 60},
                    },
                    "required": ["title"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["kind", "cells"],
        "additionalProperties": False,
    },
}

SUPPORTED_BLOCK_KINDS = tuple(BLOCK_KIND_SCHEMAS)


def build_semantic_deck_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 80},
                    "theme": {"type": "string", "enum": list(SUPPORTED_THEMES)},
                    "language": {"type": "string", "minLength": 2, "maxLength": 16},
                    "author": {"type": "string", "minLength": 1, "maxLength": 40},
                    "version": {"type": "string", "minLength": 1, "maxLength": 10},
                },
                "required": ["title", "theme", "language", "author", "version"],
                "additionalProperties": False,
            },
            "slides": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "slide_id": {"type": "string", "minLength": 1, "maxLength": 40},
                        "title": {"type": "string", "minLength": 2, "maxLength": 60},
                        "intent": {"type": "string", "enum": list(SUPPORTED_SLIDE_INTENTS)},
                        "subtitle": {"type": "string", "maxLength": 80},
                        "key_message": {"type": "string", "maxLength": 100},
                        "anti_argument": {"type": "string", "maxLength": 120},
                        "data_sources": {
                            "type": "array",
                            "maxItems": 4,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "claim": {"type": "string", "minLength": 1, "maxLength": 60},
                                    "source": {"type": "string", "minLength": 1, "maxLength": 80},
                                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                },
                                "required": ["claim", "source", "confidence"],
                                "additionalProperties": False,
                            },
                        },
                        "blocks": {
                            "type": "array",
                            "minItems": 0,
                            "maxItems": 4,
                            "items": {
                                "anyOf": [copy.deepcopy(schema) for schema in BLOCK_KIND_SCHEMAS.values()]
                            },
                        },
                    },
                    "required": ["slide_id", "title", "intent", "blocks"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["meta", "slides"],
        "additionalProperties": False,
    }
