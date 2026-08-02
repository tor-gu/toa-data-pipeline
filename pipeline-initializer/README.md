# pipeline-initializer

First step of the state machine. Normalizes and validates pipeline arguments.

## Input

| Field | Default | Notes |
|---|---|---|
| `rebuild` | `false` | must be a boolean |
| `num_executors` | `1` | must be an integer ≥ 1 |

Both fields are optional, so `{}` is a valid execution input.

Unknown fields are logged and dropped.

## Output

```json
{ "rebuild": false, "num_executors": 1 }
```

`InitializePipeline` writes this to `$`, replacing the raw execution input. 


## Validation

Values are checked, never coerced: `"true"` and `"4"` are rejected rather than converted. Note that `true` is not accepted for `num_executors` even though `bool` is a subclass of `int` in Python.

A rejection raises `InvalidInputError`, which the state's `Catch` routes to `FinalizeFailure`.

