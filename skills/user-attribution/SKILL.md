---
description: Generate and validate Traceable custom user attribution JSON configurations. TRIGGER when the user asks to create user attribution rules, extract user identity from HTTP requests/responses, configure custom authentication in Traceable, or work with projector chains for user ID/role/scope extraction.
---

# Traceable Custom User Attribution Config

Generate, validate, and iterate on Traceable custom user attribution JSON configurations that extract user identity from HTTP traffic.

## Development Process

### Phase 1: Gather Requirements

Ask the user (skip what's already answered):

1. **Where is the user identity?** Request header, request body, response body, response header, or cookie?
2. **What auth scheme?** Basic Auth, Bearer JWT, API Key, OAuth token response, login form POST, or other?
3. **What to extract?** User ID (`enduser.id`), role (`enduser.role`), scopes (`session.scopes`), auth type (`traceableai.auth.types`)?
4. **Conditional on URL?** Should this rule only apply to certain URL patterns?
5. **Sample data?** A sample HTTP request/response showing the auth data (needed for validation).

### Phase 2: Generate Config

1. Select the matching pattern from the Pattern Cookbook below
2. Adapt it to the user's requirements
3. Save the config:
   ```bash
   mkdir -p ./ua-configs
   ```
   Write to `./ua-configs/<descriptive-name>.json`
4. **Display the config to the user** — after saving, print the full JSON config content in a fenced code block so the user can review it

### Phase 3: Validate

The validation script (`scripts/validate.py`) tests configs against sample HTTP attributes.

**Bootstrap venv** (first run only — idempotent, safe to re-run):
```bash
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." 2>/dev/null && pwd || echo "$HOME/.claude/skills/user-attribution")"
if [ ! -f "$SKILL_DIR/.venv/bin/activate" ]; then
  python3 -m venv "$SKILL_DIR/.venv"
  "$SKILL_DIR/.venv/bin/pip" install -q -r "$SKILL_DIR/scripts/requirements.txt"
fi
```

All `python` commands below must use the skill's venv python:
```
SKILL_PYTHON="$SKILL_DIR/.venv/bin/python"
```

**Run with a built-in fixture:**
```bash
"$SKILL_PYTHON" "$SKILL_DIR/scripts/validate.py" --config-file ./ua-configs/<name>.json --fixture basic_auth
```

**Run with custom attributes from a file:**
```bash
"$SKILL_PYTHON" "$SKILL_DIR/scripts/validate.py" --config-file ./ua-configs/<name>.json --attributes-file attrs.json
```

**Run with inline attributes:**
```bash
"$SKILL_PYTHON" "$SKILL_DIR/scripts/validate.py" --config-file ./ua-configs/<name>.json \
  --attributes-inline '{"http.request.header.authorization": "Bearer eyJ..."}'
```

For complex attributes with nested quotes, write them to a temp file first.

**List available fixtures:**
```bash
"$SKILL_PYTHON" "$SKILL_DIR/scripts/validate.py" --list-fixtures
```

### Phase 4: Iterate

After running validation, **always display the results to the user** in a clear summary:

1. State what test was run (which config file, which fixture/attributes)
2. Show the outcome:
   - For each extracted output key, show the key and its value
   - Clearly indicate PASS or FAIL for each expected extraction
3. If there were issues, show the relevant log lines

Then parse the JSON output internally to decide next steps:

- **`success: true` + expected output** — Done. Go to Phase 5.
- **`success: true` + empty output** — Chain not matching. Check `logs` for "did not match" messages:
  - Wrong attribute key name (typo, wrong case)?
  - Regex pattern doesn't match value?
  - Conditional predicate not firing (URL pattern wrong)?
- **`success: false`** — Structural error. Check `error` field:
  - Missing `attributeRule`?
  - Unknown projector type?
  - Invalid JSON syntax?

Fix the config and re-run validation. Repeat until correct.

### Phase 5: Deliver

1. Show the final JSON config
2. Explain each step of the projector chain in plain language
3. Tell the user: "Paste this JSON into the Custom User Attribution configuration in the Traceable platform UI"

---

## JSON Config Structure

Every config is a recursive tree of projectors connected by `attributeRule` nodes:

```
{
  "projector": {
    "<ProjectorType>": {
      ...projector-specific fields...
      "attributeRule": {                    // Next step in chain
        "projector": { ... }               // Another projector (recurse)
        // OR
        "initialActions": [ ... ]          // Terminal: store results
      }
    }
  }
}
```

### Terminal Actions

When the chain reaches its final value, use `initialActions` to store output:

```json
"initialActions": [
  {
    "attributeAddition": {
      "attributeKey": "enduser.id",
      "valueProjectionRule": {
        "projector": { "noOpProjector": {} }
      }
    }
  }
]
```

- **`attributeAddition`**: Sets a key to the current value. Use `noOpProjector` to store as-is, or another projector to transform.
- **`attributeArrayAppend`**: Appends the value to an array. Same structure. Use for multi-valued fields like `traceableai.auth.types`.

An `attributeRule` must contain EITHER `projector` OR `initialActions`, never both.

---

## Projector Types

### `attributeProjector`
Reads a value from HTTP attributes by key.
```json
{ "attributeProjector": { "attributeKey": "http.request.header.authorization", "attributeRule": { ... } } }
```

### `base64Projector`
Base64-decodes the current value.
```json
{ "base64Projector": { "attributeRule": { ... } } }
```

### `regexCaptureGroupProjector`
Extracts via regex. **Must have exactly one capture group `(...)`**. Use `(?:...)` for non-capturing.
```json
{ "regexCaptureGroupProjector": { "regexCaptureGroup": "^Bearer (.*)$", "attributeRule": { ... } } }
```

### `jsonProjector`
Extracts from a JSON string using JSONPath.
```json
{ "jsonProjector": { "jsonPathRule": { "key": "$.username", "attributeRule": { ... } } } }
```

### `jwtProjector`
Decodes JWT and extracts a claim or header. Input must be raw JWT (no "Bearer " prefix).
```json
{ "jwtProjector": { "claimRule": { "key": "sub", "attributeRule": { ... } } } }
{ "jwtProjector": { "headerRule": { "key": "alg", "attributeRule": { ... } } } }
```

### `valueProjector`
Returns a literal string. Only used inside `initialActions` as a `valueProjectionRule`.
```json
{ "valueProjector": { "value": "Basic" } }
```

### `noOpProjector`
Passes through current value unchanged. Only used inside `initialActions` as a `valueProjectionRule`.
```json
{ "noOpProjector": {} }
```

### `conditionalProjector`
Executes nested rule only if a predicate matches.
```json
{
  "conditionalProjector": {
    "predicate": {
      "attributePredicate": {
        "namePredicate": { "operator": "COMPARISON_OPERATOR_EQUALS", "value": "http.url" },
        "valuePredicate": { "operator": "COMPARISON_OPERATOR_MATCHES_REGEX", "value": ".*/login" }
      }
    },
    "attributeRule": { ... }
  }
}
```

---

## Attribute Keys

### Input Keys

| Pattern | Description | Example |
|---------|-------------|---------|
| `http.url` | Full request URL | `https://api.example.com/login` |
| `http.request.header.<name>` | Request header (lowercase) | `http.request.header.authorization` |
| `http.response.header.<name>` | Response header (lowercase) | `http.response.header.x-user-id` |
| `http.request.body` | Request body string | `{"username":"john"}` |
| `http.response.body` | Response body string | `{"access_token":"eyJ..."}` |
| `http.request.cookie.<name>` | Request cookie | `http.request.cookie.session_id` |
| `http.response.cookie.<name>` | Response cookie | `http.response.cookie.token` |

**Header names must be lowercase** in attribute keys.

### Output Keys

| Key | Description |
|-----|-------------|
| `enduser.id` | Primary user identifier |
| `enduser.role` | User role |
| `session.scopes` | OAuth/permission scopes |
| `traceableai.auth.types` | Auth type (use `attributeArrayAppend`) |
| `enduser.id.rule` | Rule identifier label |
| `token.jwt.payload.<header>.<claim>` | JWT claim values (anomaly rules) |

---

## Pattern Cookbook

### Pattern A: Basic Auth Header

Extract username from `Authorization: Basic <base64(user:pass)>`.

Chain: `attributeProjector` -> `regexCaptureGroupProjector` (strip "Basic ") -> `base64Projector` -> `regexCaptureGroupProjector` (extract before `:`) -> `initialActions`

See: `examples/basic_auth_header.json`
Test: `python scripts/validate.py --config-file examples/basic_auth_header.json --fixture basic_auth`
Expected: `enduser.id: "user"`, `traceableai.auth.types: ["Basic"]`

### Pattern B: JWT Bearer Token Claim

Extract user ID from JWT `sub` claim in `Authorization: Bearer <jwt>`.

Chain: `attributeProjector` -> `regexCaptureGroupProjector` (strip "Bearer ") -> `initialActions` with `jwtProjector` per claim

See: `examples/jwt_bearer_claim.json`
Test: `python scripts/validate.py --config-file examples/jwt_bearer_claim.json --fixture jwt_bearer`
Expected: `enduser.id: "user123"`, `enduser.role: "admin"`, `traceableai.auth.types: ["Bearer"]`

### Pattern C: Request Body JSON Field

Extract username from login POST body, conditional on URL.

Chain: `conditionalProjector` (URL check) -> `attributeProjector` (body) -> `jsonProjector` -> `initialActions`

See: `examples/request_body_login.json`
Test: `python scripts/validate.py --config-file examples/request_body_login.json --fixture request_body_login`
Expected: `enduser.id: "john.doe"`

### Pattern D: Response Body JSON Field

Extract scope from OAuth token response body, conditional on URL.

Chain: `conditionalProjector` (URL check) -> `attributeProjector` (response body) -> `jsonProjector` -> `initialActions`

See: `examples/response_body_oauth.json`
Test: `python scripts/validate.py --config-file examples/response_body_oauth.json --fixture response_body_token`
Expected: `session.scopes: "read write admin"`

### Pattern E: Custom Header

Read user ID directly from a custom header.

Chain: `attributeProjector` -> `regexCaptureGroupProjector` (capture all) -> `initialActions`

See: `examples/custom_header.json`
Test: `python scripts/validate.py --config-file examples/custom_header.json --fixture custom_header`
Expected: `enduser.id: "user-12345"`

### Pattern F: Conditional Header Presence

Extract only if a header exists (non-empty).

Use `conditionalProjector` with `valuePredicate` regex `.+` to check presence before extraction.

See: `examples/conditional_header_check.json`
Test: `python scripts/validate.py --config-file examples/conditional_header_check.json --fixture custom_header`
Expected: `enduser.id: "ak_prod_12345"`, `traceableai.auth.types: ["ApiKey"]`

### Pattern G: JWT Anomaly Rules

Extract multiple JWT claims (iss, sub, iat, exp) for anomaly detection.

Chain: `conditionalProjector` (Bearer check) -> `attributeProjector` -> `regexCaptureGroupProjector` -> `initialActions` with multiple `jwtProjector` entries

See: `examples/jwt_anomaly_rules.json`
Test: `python scripts/validate.py --config-file examples/jwt_anomaly_rules.json --fixture jwt_bearer`

### Pattern H: Response JWT Claim

Extract user ID from a JWT in a response header.

Chain: `conditionalProjector` (header exists) -> `attributeProjector` -> `regexCaptureGroupProjector` -> `initialActions` with `jwtProjector`

See: `examples/response_jwt_claim.json`

---

## Engine Limitations

- **Conditional operator**: Only `COMPARISON_OPERATOR_MATCHES_REGEX` is supported for `valuePredicate`. For exact matching, use regex `^exact-value$`.
- **Header names**: Must be lowercase in attribute keys.
- **JWT input**: `jwtProjector` expects raw JWT (three dot-separated segments). Always strip "Bearer " prefix first via `regexCaptureGroupProjector`.

## Common Mistakes

1. **Missing `"projector"` wrapper**: Every projector type must be inside `"projector": { "<type>": {...} }`.
2. **Missing `attributeRule`**: Every projector except `noOpProjector`/`valueProjector` needs an `attributeRule`.
3. **Both `projector` and `initialActions`**: An `attributeRule` must have ONE, never both.
4. **Regex without capture group**: `regexCaptureGroupProjector` requires exactly one `(...)`. Use `(?:...)` for non-capturing.
5. **JWT without stripping prefix**: `"Bearer eyJ..."` fed to `jwtProjector` will fail.
6. **Wrong attribute key case**: Use `http.request.header.authorization` not `Authorization`.
7. **`valueProjector` with `attributeRule`**: `valueProjector` only goes inside `initialActions`. It does not chain.

## Test Fixtures

Built-in fixtures in `scripts/fixtures/`:

| Fixture | Scenario |
|---------|----------|
| `basic_auth` | `Authorization: Basic dXNlcjpwYXNzd29yZA==` (user:password) |
| `jwt_bearer` | `Authorization: Bearer <jwt>` with sub=user123, role=admin, iss, aud |
| `request_body_login` | POST body `{"username":"john.doe"}` to `/login` |
| `response_body_token` | OAuth response with access_token, scope at `/v1/oauth2/token` |
| `custom_header` | X-User-Id=user-12345, X-API-Key, X-User-Role=admin |
