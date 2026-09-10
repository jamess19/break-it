"""Optional tool param + null: Groq validate schema server-side, model hay emit null.

Fix 2 biên:
- provider (openai `_tool_to_dict`) nới optional param → type nhận "null" khi GỬI đi
- provider (`_dict_to_message`) dọn arg null qua `util.clean_arguments` khi NHẬN về
"""

from app.domain.tool import ToolDef
from app.providers.openai import OpenAIProvider
from app.util import clean_arguments


def _wire(params: dict) -> dict:
    td = ToolDef(name="t", description="x", parameters=params)
    return OpenAIProvider._tool_to_dict(td)["function"]["parameters"]["properties"]


def test_optional_param_nullable_in_wire_schema():
    props = _wire({
        "type": "object",
        "properties": {"status": {"type": "string"}, "project": {"type": "string"}},
    })
    assert props["status"]["type"] == ["string", "null"]
    assert props["project"]["type"] == ["string", "null"]


def test_required_param_stays_strict():
    props = _wire({
        "type": "object",
        "properties": {"fact": {"type": "string"}, "category": {"type": "string"}},
        "required": ["fact"],
    })
    assert props["fact"]["type"] == "string"
    assert props["category"]["type"] == ["string", "null"]


def test_nested_array_item_optional_is_nullable():
    props = _wire({
        "type": "object",
        "properties": {
            "slots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "start_minute": {"type": "integer"},
                    },
                    "required": ["task_id"],
                },
            },
        },
        "required": ["slots"],
    })
    item_props = props["slots"]["items"]["properties"]
    assert item_props["task_id"]["type"] == "integer"
    assert item_props["start_minute"]["type"] == ["integer", "null"]


def test_clean_arguments():
    assert clean_arguments({"a": None, "b": 1, "c": None}) == {"b": 1}
    assert clean_arguments({"x": 0, "y": False, "z": ""}) == {"x": 0, "y": False, "z": ""}


def test_provider_strips_null_args_when_parsing():
    msg = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "function": {"name": "list_tasks",
                                      "arguments": '{"project": null, "status": "todo"}'}}
        ],
    }
    parsed = OpenAIProvider._dict_to_message(msg)
    assert parsed.tool_calls[0].arguments == {"status": "todo"}
