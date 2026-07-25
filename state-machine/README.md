# state-machine

This is the AWS Step Functions state machine definition that drives the pipeline. The `state_machine.json.tftpl` file is a terraform template.

## Flow

```mermaid
flowchart TD
    ConsolidatePar --> Check{CheckIfFilesProcessed}
    Check -->|files_processed > 0| UpdateScores
    Check -->|default| FinalizeSuccess
    UpdateScores --> EnrichScores
    EnrichScores --> Par

    subgraph ConsolidatePar["ConsolidateNamesAndResults (Parallel)"]
        ConsolidateNames
        ConsolidateResults
    end

    subgraph Par["BuildStatisticsAndViz (Parallel)"]
        BuildStatistics
        BuildViz
    end

    Par --> SyncDynamoDB
    SyncDynamoDB --> FinalizeSuccess
    FinalizeSuccess --> Succeeded([Execution succeeded])

    ConsolidatePar -.->|error| FinalizeFailure
    UpdateScores -.->|error| FinalizeFailure
    EnrichScores -.->|error| FinalizeFailure
    Par -.->|error| FinalizeFailure
    SyncDynamoDB -.->|error| FinalizeFailure
    FinalizeFailure --> ExecutionFailed([Execution failed])
```

## Notes

Every task retries `Lambda.TooManyRequestsException` — 10 attempts from 5s with a
backoff rate of 2 — and catches `States.ALL` to `FinalizeFailure`, which logs the
error and then transitions to a `Fail` state.

Neither `Parallel` state's branches have a `Catch` of their own; the `Parallel`
state catches for both, so a failure in either branch aborts the pair.

`FinalizeSuccess` and `FinalizeFailure` have no `Retry` or `Catch`. An error in
either fails the execution directly.

## Simultaneous uploads

The normal use case is that results are uploaded one -- or perhaps a few -- at a time. A large burst of results might be uploaded in a test environment, or when reloading all the data from scratch (for some reason).  This section describes what happens when multiple results are uploaded simultaneously, or nearly so.

**Each upload triggers a run of the state machine**. There are two mechanisms to keep that safe.

**Concurrency limiting.** Every pipeline Lambda except results-watcher and
pipeline-finalizer is capped at `reserved_concurrent_executions = 1`. A second
concurrent invocation is throttled with `Lambda.TooManyRequestsException` — which triggers a retry. So, overlapping executions serialize a step at a time.

**Short-circuiting.** results-consolidator takes everything in
`results/unprocessed/`, not just the file that triggered it. Executions behind it find nothing, return `files_processed: 0`, and jump to the finalizer.

As long as every execution succeeds (eventually), the end state is correct. 

### Gap: retries exhausted waiting for a post-consolidation lambda to complete

If a large number of results are uploaded in rapid succession, it is conceivable that overlapping executions queue up at some step after `results-consolidator` waiting for a lambda (e.g. `scores-updater`) to complete. If the retry budget is eventually exhausted, results will have been consolidated and moved to the `processed` folder, without being processed all the way to the end. If no subsequently handled results have an earlier date, they will never be processed.

This scenario would involve 10 attempts spanning about 85 minutes. It would be reported as a pipeline FAILURE.

This case could be handled by adding a manual trigger of a full-refresh, but this is not currently implemented. (TODO)

