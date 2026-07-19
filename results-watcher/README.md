# results-watcher

Entry point of the pipeline. Fires on `s3:ObjectCreated:*` for `.json` uploads under
`results/unprocessed/` and starts a state machine execution.

The S3 event is not read or passed on — the execution input is an empty object, and
results-consolidator picks up whatever is sitting in the folder. So an upload of
several files at once starts several executions; see
[Simultaneous uploads](../state-machine/README.md#simultaneous-uploads) for how those
are kept from colliding.
