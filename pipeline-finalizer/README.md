# pipeline-finalizer

Terminal step of the state machine. Logs the outcome to CloudWatch and nothing else.


## Input

| Field | Notes |
|---|---|
| `status` | `"success"` or `"failure"`; anything else is logged as a failure |
| `error` | the caught Step Functions error, failure path only |

`FinalizeSuccess` passes `status: "success"` and ends the execution — reached both on
normal completion and when results-consolidator finds nothing new. `FinalizeFailure`
is the `Catch` target of every task and passes the error along.

The Lambda never raises; the failure path logs a warning and returns. What marks the
execution FAILED is the `Fail` state that follows it.
