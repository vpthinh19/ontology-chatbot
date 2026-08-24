# CPU ONNX production runtime and image

## Goal

Replace the production CUDA runtime with a compact CPU-only ONNX deployment so
Lightning can restore a zero-replica service without pulling a multi-gigabyte
GPU image. Preserve streamed chat behavior and bounded overload handling while
allowing four lookups to use an eight-vCPU replica without blocking the ASGI
event loop.

## Scope

This change removes CUDA only from production and deployment surfaces:

- the serving dependency set and lock resolution used by the image;
- the Docker base image and runtime environment;
- the HTTP-serving CLI and ONNX production loader;
- release workflow steps, production smoke tests, and deployment comments;
- tests that describe the serving runtime.

Research and training retain GPU support. `torch.cuda`, GPU training code,
historical benchmark results, and research-only CUDA dependencies remain in the
repository and may remain represented in the universal `uv.lock`. They must not
be installed by `uv sync --extra inference` or copied into the production image.

The released classifier remains the existing FP16 artifact at
`vpthinh19/ntu-ontology-xlmr/onnx-xlmr`. INT8 quantization is a separate future
change because it would alter the model artifact and require a new accuracy
acceptance decision.

## Observed baseline

The current Docker Hub `latest` artifact reports a compressed size of about
2.98 GB. Its runtime combines `nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04`,
`onnxruntime-gpu`, and the 572 MB FP16 classifier artifact.

The current classifier already executes successfully through
`CPUExecutionProvider`. On the development host, the measured behavior for one
shared session was:

| Intra-op threads | Concurrent calls | Throughput | Median inference |
|---:|---:|---:|---:|
| 8 | 1 | 9.6/s | 103.3 ms |
| 4 | 2 | 17.4/s | 109.0 ms |
| 2 | 4 | 29.2/s | 122.0 ms |
| 1 | 8 | 41.5/s | 161.8 ms |

Twenty end-to-end ontology lookups also completed successfully with four Python
workers sharing one ONNX session and one read-only Oxigraph-backed RDF graph.
These measurements select the balanced two-thread/four-call configuration; they
are not performance guarantees for Lightning hardware.

## Runtime architecture

Each replica runs one Uvicorn process, one ONNX Runtime session, and one
read-only ontology graph. Multiple Uvicorn worker processes are deliberately
excluded because every process would load another 572 MB model and ontology,
increasing memory use and cold-start work.

The existing `TurnGate` continues to admit at most four complete chat turns and
queue at most twenty. A turn holds its slot from its first LLM request through
the final streamed response, preserving the existing external-model cost bound.

The agent tool becomes explicitly asynchronous. It acquires a lookup semaphore
and sends the synchronous tokenizer, ONNX inference, and SPARQL work through
`asyncio.to_thread`. The semaphore admits four lookups at once. This explicit
boundary replaces reliance on the agent SDK's implicit handling of synchronous
tools and makes the concurrency limit testable by this project.

Each ONNX call uses two intra-op threads. Four simultaneous calls therefore
have a worst-case budget of eight native compute threads. The session uses
`ORT_SEQUENTIAL`; inter-op parallel execution is disabled because the classifier
graph does not need another graph-level thread pool. ONNX graph optimization
remains fully enabled.

The shared session and graph remain immutable after startup. No per-request
model copy, graph copy, or process-local conversational state is introduced.
Consequently, Lightning can distribute later requests to any replica; the
browser continues to send its bounded conversation history with every request.

## Interfaces and configuration

The production loader changes to this contract:

```python
OnnxClassifierGenerator.load(
    model_dir,
    *,
    graph=None,
    intra_op_threads=2,
)
```

It always constructs a session with `providers=["CPUExecutionProvider"]`.
The `device` parameter, CUDA preload, provider fallback control, and GPU-provider
validation are removed.

The serving CLI removes `--device` and no longer reads `ONTCHATBOT_DEVICE`. It
adds two positive-integer settings:

- `--onnx-threads`, environment `ONTCHATBOT_ONNX_THREADS`, default `2`;
- `--lookup-workers`, environment `ONTCHATBOT_LOOKUP_WORKERS`, default `4`.

Invalid, zero, or negative values stop startup with a concise configuration
error. Startup logs the effective values and warns, without refusing to start,
when their product exceeds the CPU affinity visible to the process. This avoids
silently oversubscribing a smaller custom deployment while not assuming that
host CPU count exactly matches a container's quota.

`build_agent` and `build_tool` accept the lookup-worker value explicitly. The
tool wrapper owns the semaphore; it releases the slot on success, exception, or
request cancellation.

## Request and overload flow

1. `POST /chat` validates and bounds the request body asynchronously.
2. `TurnGate` admits up to four turns. Later turns receive their queue position.
3. LLM requests and SSE output remain asynchronous and consume no lookup worker
   while waiting on the network.
4. A tool call waits for one of four lookup slots, then runs the complete lookup
   in a worker thread.
5. ONNX uses at most two native intra-op threads for that lookup. All keywords in
   one tool call continue to be a single real ONNX batch.
6. SPARQL executes in the same worker after classification, and the result returns
   to the async agent runner.
7. The final answer continues streaming to the browser.

If four chat turns are active, later turns use the existing twenty-place queue.
A queued turn still times out after fifteen seconds, and a request beyond the
queue ceiling receives the existing busy event immediately. Multiple replicas
multiply this bounded capacity independently.

Cancelling an `asyncio.to_thread` await cannot stop native work already running.
The inference is short, so a disconnected request may finish its current lookup
and discard the result. The semaphore must still be released, and no replacement
job or unbounded background task is created.

## Dependency and image layout

The inference extra contains only serving dependencies:

- `fastapi` without the `standard` extra;
- `uvicorn`;
- `onnxruntime` rather than `onnxruntime-gpu`;
- `openai-agents`;
- `tokenizers`.

`huggingface-hub` moves out of the inference environment. It remains available
to research and publishing commands, while the Docker model-fetch stage uses an
isolated temporary uv environment. This keeps Hub tooling and `hf-xet` out of the
runtime virtualenv.

The Dockerfile uses three stages based on `python:3.12-slim-bookworm`:

1. `builder` creates the frozen production virtualenv and installs the package;
2. `model-fetcher` downloads only `onnx-xlmr/*` at the resolved Hub revision;
3. `runtime` applies OS security updates and copies only the virtualenv, source,
   ontology resources, and classifier files.

The runtime stage does not contain uv, Hugging Face tooling, compilers, tests,
frontend files, documentation, CUDA libraries, NVIDIA wheels, or model caches.
Python bytecode compilation remains enabled because a small disk increase reduces
imports during cold start.

The FP16 model is intentionally baked into the image. Downloading it during
container startup would make every new replica depend on Hub availability and
would merely move, rather than remove, the cold-start transfer.

## CI and release

The release workflow deletes the CUDA-specific runner cleanup and CUDA-runtime
verification steps. The large-runner cleanup scripts that exist only for the GPU
image are removed.

A CPU runtime verification script checks the built image for:

- Python 3.12;
- a successful import of the CPU `onnxruntime` distribution;
- a session whose provider list is exactly `CPUExecutionProvider` for the released
  classifier;
- absence of GPU runtime distributions and NVIDIA site-packages;
- successful model loading with the configured two-thread session.

The existing detached `/healthz` smoke test remains, without `ONTCHATBOT_DEVICE`.
Trivy OS scanning, immutable version tags, `latest`, and the Hugging Face revision
record in the GitHub release remain unchanged.

Because version `2.1.2` is already tagged and the workflow only releases an
untagged project version, implementation bumps the project to `3.0.0`. Removing
the public `--device` serving option and changing the required deployment hardware
is a breaking production-interface change even though the REST API is unchanged.

CI records `docker image inspect` size and Docker history after the build. The
target is a compressed registry artifact below approximately 1 GB. Before push,
the enforceable acceptance is structural—no GPU runtime content—and comparative:
the CPU image must be materially smaller than the released GPU image. If the Hub
reports more than 1 GB after release, layer-size evidence determines the next
optimization; no runtime library is manually pruned or patched to hit the number.

## Error handling

- Missing classifier files still fail startup before the port binds.
- Invalid CPU concurrency settings fail startup before the port binds.
- Failure to construct a CPU session is fatal; there is no alternate provider.
- Lookup exceptions retain the existing bounded tool result behavior.
- Pool saturation waits for a bounded lookup slot rather than creating threads.
- Turn queue overflow, queue timeout, LLM timeout, cancellation, and SSE error
  messages retain their existing contracts.

## Testing and acceptance

Tests are written before their production changes and cover:

- the serving CLI rejects the removed `--device` option and accepts positive CPU
  settings from flags and environment;
- invalid CPU settings stop startup;
- the loader passes the expected CPU provider and session options to ONNX Runtime;
- the production code contains no CUDA preload or GPU fallback branch;
- the lookup semaphore never permits more than four concurrent lookups;
- a blocked lookup does not block `/healthz` or SSE work on the event loop;
- one shared session and graph return stable results under four concurrent calls;
- cancellation and exceptions release lookup slots;
- the existing turn gate, cold-start, queue, retry, history, and frontend suites
  remain green.

Verification runs the complete Python and frontend test suites, builds the real
Docker image, runs CPU-runtime verification, starts the container, reaches
`/healthz`, records startup time and image size, and runs a direct CPU classifier
benchmark. The 390-question classifier evaluation is rerun to confirm that using
the unchanged FP16 graph through `CPUExecutionProvider` preserves the released
predictions and metrics.

## Deployment migration

The new `latest` image needs no GPU selection or passthrough. Lightning should use
the eight-vCPU CPU-only provider, remove `ONTCHATBOT_DEVICE`, and optionally set
the two new variables only when overriding the balanced defaults. Port `8000`,
health route `/healthz`, chat route `/chat`, LLM secrets, TokenAuth, Vercel proxy,
and scale range `0–1` remain unchanged.
