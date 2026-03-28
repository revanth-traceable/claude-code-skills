#!/usr/bin/env python3
"""Validate a Traceable custom user attribution JSON config against sample HTTP attributes.

The validation script runs the user attribution engine (ua.py) against a config
and sample attributes, outputting structured JSON results.

Usage:
    python scripts/validate.py --config-file config.json --attributes-file attrs.json
    python scripts/validate.py --config-file config.json --attributes-inline '{"http.url":"..."}'
    python scripts/validate.py --config-inline '...' --attributes-inline '...'
    python scripts/validate.py --config-file config.json --fixture basic_auth

Output: JSON to stdout with keys: success, output, logs, error
Exit code: 0 if config ran successfully, 1 on error
"""

import argparse
import json
import os
import sys
import traceback

# Add scripts directory to path so we can import ua
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from ua import UserAttribution, log_capture_string

FIXTURES_DIR = os.path.join(SCRIPT_DIR, "fixtures")


def load_json(file_path=None, inline=None, label="input"):
    if file_path:
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"{label} file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"{label} file contains invalid JSON: {e}")
    elif inline:
        try:
            return json.loads(inline)
        except json.JSONDecodeError as e:
            raise ValueError(f"{label} inline string is invalid JSON: {e}")
    else:
        raise ValueError(f"No {label} provided")


def list_fixtures():
    """List available fixture files."""
    if not os.path.isdir(FIXTURES_DIR):
        return []
    return [f.replace(".json", "") for f in os.listdir(FIXTURES_DIR) if f.endswith(".json")]


def main():
    # Handle --list-fixtures before full arg parsing (it needs no other args)
    if "--list-fixtures" in sys.argv:
        fixtures = list_fixtures()
        if fixtures:
            print("Available fixtures:")
            for f in sorted(fixtures):
                fixture_path = os.path.join(FIXTURES_DIR, f"{f}.json")
                with open(fixture_path, "r") as fh:
                    data = json.load(fh)
                keys = ", ".join(data.keys())
                print(f"  {f}: {keys}")
        else:
            print("No fixtures found.")
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="Validate a user attribution JSON config against sample attributes"
    )

    config_group = parser.add_mutually_exclusive_group(required=True)
    config_group.add_argument("--config-file", help="Path to config JSON file")
    config_group.add_argument("--config-inline", help="Inline config JSON string")

    attrs_group = parser.add_mutually_exclusive_group(required=True)
    attrs_group.add_argument("--attributes-file", help="Path to attributes JSON file")
    attrs_group.add_argument("--attributes-inline", help="Inline attributes JSON string")
    attrs_group.add_argument(
        "--fixture",
        help="Name of a built-in fixture (e.g., basic_auth, jwt_bearer). "
             f"Available: {', '.join(list_fixtures())}",
    )

    args = parser.parse_args()

    # Flush any previous log data
    log_capture_string.getvalue()

    # Load config
    try:
        config = load_json(args.config_file, args.config_inline, "config")
    except ValueError as e:
        result = {"success": False, "output": {}, "logs": "", "error": str(e)}
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # Load attributes
    try:
        if args.fixture:
            fixture_path = os.path.join(FIXTURES_DIR, f"{args.fixture}.json")
            if not os.path.exists(fixture_path):
                available = ", ".join(list_fixtures())
                raise ValueError(
                    f"Fixture '{args.fixture}' not found. Available: {available}"
                )
            attributes = load_json(file_path=fixture_path, label="fixture")
        else:
            attributes = load_json(args.attributes_file, args.attributes_inline, "attributes")
    except ValueError as e:
        result = {"success": False, "output": {}, "logs": "", "error": str(e)}
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # Run the engine
    try:
        ua = UserAttribution(config, attributes)
        output = {}
        for k, v in ua.output.items():
            if isinstance(v, list):
                output[k] = [str(item) for item in v]
            else:
                output[k] = str(v)
        result = {
            "success": True,
            "output": output,
            "logs": log_capture_string.getvalue(),
            "error": None,
        }
    except Exception as e:
        result = {
            "success": False,
            "output": {},
            "logs": log_capture_string.getvalue(),
            "error": f"{e}\n{traceback.format_exc()}",
        }

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
