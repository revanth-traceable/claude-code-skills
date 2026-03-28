# User Attribution Config Evaluation Guide

## Overview

The validation script (`scripts/validate.py`) tests user attribution JSON configs against sample HTTP attributes to verify they correctly extract user identity.

## Running Evaluations

### Prerequisites

Install dependencies from the skill directory:

```bash
pip install -r scripts/requirements.txt
```

### Using Built-in Fixtures

List available fixtures:

```bash
python scripts/validate.py --list-fixtures
```

Run a config against a fixture:

```bash
python scripts/validate.py --config-file examples/basic_auth_header.json --fixture basic_auth
```

### Using Custom Attributes

From a file:

```bash
python scripts/validate.py --config-file my_config.json --attributes-file my_attrs.json
```

Inline:

```bash
python scripts/validate.py --config-file my_config.json --attributes-inline '{"http.request.header.authorization": "Bearer eyJ..."}'
```

### Using Inline Config

```bash
python scripts/validate.py --config-inline '{"projector":{"attributeProjector":{"attributeKey":"http.request.header.x-user-id","attributeRule":{"initialActions":[{"attributeAddition":{"attributeKey":"enduser.id","valueProjectionRule":{"projector":{"noOpProjector":{}}}}}]}}}}' --fixture custom_header
```

## Output Format

The script outputs JSON to stdout:

```json
{
  "success": true,
  "output": {
    "enduser.id": "user123",
    "enduser.role": "admin"
  },
  "logs": "Running projector attributeProjector\n...",
  "error": null
}
```

| Field | Description |
|-------|-------------|
| `success` | `true` if config executed without exceptions |
| `output` | Dict of extracted attribute key-value pairs |
| `logs` | Engine execution trace (projector chain steps) |
| `error` | Error message if `success` is `false`, otherwise `null` |

Exit code: `0` on success, `1` on error.

## Interpreting Results

### Success with Output

The config works correctly. Verify the output keys and values match expectations.

### Success with Empty Output

The projector chain didn't produce any output. Common causes:

- **Wrong attribute key**: Check spelling and case of attribute keys in the config. Header names must be lowercase.
- **Regex not matching**: The `regexCaptureGroupProjector` pattern doesn't match the input value. Check the `logs` for "Regex did not match" messages.
- **Conditional not firing**: The `conditionalProjector` predicate doesn't match. Check URL pattern or header value in the predicate.
- **Missing attribute**: The attribute key referenced in the config doesn't exist in the test attributes.

### Failure with Error

A structural or runtime error occurred. Common causes:

- **"Projector not found"**: Missing `projector` key wrapper or unknown projector type.
- **"Attribute rule not found"**: An `attributeRule` exists but has neither `projector` nor `initialActions`.
- **JSON parse error**: Invalid JSON syntax in config or attributes.

## Available Fixtures

| Fixture | Attributes | Use With |
|---------|-----------|----------|
| `basic_auth` | Authorization header with Basic auth | Basic auth extraction configs |
| `jwt_bearer` | Authorization header with JWT Bearer token (sub=user123, role=admin) | JWT claim extraction configs |
| `request_body_login` | POST to /login with username in body | Request body extraction configs |
| `response_body_token` | OAuth token response at /v1/oauth2/token with scope field | Response body extraction configs |
| `custom_header` | X-User-Id, X-API-Key, X-User-Role headers | Custom header extraction configs |

## Creating Custom Fixtures

A fixture is a JSON file with attribute key-value pairs representing HTTP request/response data:

```json
{
  "http.url": "https://api.example.com/endpoint",
  "http.request.header.authorization": "Bearer eyJ...",
  "http.request.header.x-custom": "value",
  "http.request.body": "{\"key\": \"value\"}",
  "http.response.body": "{\"token\": \"abc\"}",
  "http.response.header.x-user": "user123"
}
```

Place custom fixtures in `scripts/fixtures/` and reference them by name (without `.json` extension).
