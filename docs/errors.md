# Errors

`APIError` is a JSON response and an exception at the same time. Raise it from
any handler or hook and Muffin returns the response.

## Response shape

By default the body is:

```json
{"error": true, "message": "Bad Request"}
```

The status code comes from the shortcut or from `status_code`:

```python
from muffin_rest import APIError

raise APIError.BAD_REQUEST("Invalid filter")
# 400 {"error": true, "message": "Invalid filter"}

raise APIError.NOT_FOUND()
# 404 {"error": true, "message": "Nothing matches the given URI"}

raise APIError.CONFLICT("Email is already used")
# 409 {"error": true, "message": "Email is already used"}
```

Every `HTTPStatus` name works as a shortcut: `UNAUTHORIZED`, `FORBIDDEN`,
`METHOD_NOT_ALLOWED`, `UNPROCESSABLE_ENTITY`, `TOO_MANY_REQUESTS`,
`INTERNAL_SERVER_ERROR`, and so on. Use the names, not raw numbers.

Extra keyword arguments are merged into the body:

```python
raise APIError.BAD_REQUEST("Invalid filter", field="age")
# {"error": true, "message": "Invalid filter", "field": "age"}
```

A dictionary as the first argument replaces the default body entirely:

```python
raise APIError.BAD_REQUEST({"error": True, "message": "Invalid filter", "field": "age"})
```

This is how validation errors carry details:

```python
raise APIError.BAD_REQUEST("Bad request data", errors=err.messages)
```

## Errors raised by the library

| Situation | Status | Body |
| --------- | ------ | ---- |
| No authorization | `401` | default `APIError.UNAUTHORIZED` |
| Invalid JSON body | `400` | parser message |
| Schema validation failed | `400` | `message` plus `errors` |
| Invalid pagination params | `400` | `Pagination params are invalid` |
| Unknown resource | `404` | `Resource not found` |
| Invalid Peewee id | `400` | `Invalid resource ID` |
| Invalid Mongo `ObjectId` | `404` | default `NOT_FOUND` |
| Unsupported method | `405` | router response |
| Rate limit exceeded | `429` | whatever you raise |

Validation errors look like this:

```json
{
  "error": true,
  "message": "Bad request data",
  "errors": {"name": ["Missing data for required field."]}
}
```

## Handler binding

`self.api` raises `HandlerNotBindedError` when the handler was not registered
with `api.route`. The error is a `RuntimeError`. This usually means a handler
class was imported but never decorated.

`api.route` raises `InvalidEnpointError` (a `TypeError`) when the object is
neither a path string nor a `RESTBase` subclass.

## Custom routes and hooks

`APIError` works anywhere the request is handled:

```python
@PWRESTHandler.route("/pet/{id}/adopt", methods="post")
async def adopt(self, request, *, resource=None):
    if resource is None:
        raise APIError.NOT_FOUND()
    if resource.status != "available":
        raise APIError.CONFLICT("Pet is not available")
    ...
```

For errors that are not part of the API contract, let the exception propagate
and let Muffin's error handling produce the response. `APIError` is for expected
client-facing failures.
