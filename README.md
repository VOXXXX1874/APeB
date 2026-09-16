# Agent Personalization Benchmark (APeB)

APeB is an evaluation benchmark for personalized product reranking with language-model agents. Given a search query, a user's historical interactions, and a candidate set, a method predicts the ranked candidate indices most likely to contain the purchased item. This repository contains the evaluation code; the released dataset is hosted on Hugging Face.

## Included methods

- Raw LLM ranking
- ReAct
- ASA-ReAct
- DeerFlow
- VQRA
- MemAgent

All methods use the same data loader, output schema, and Recall@1/3/5 implementation. "ASA-ReAct" is a handcrafted ReAct pipeline, which only contain retrieval tool, to support endpoints without stable tool-calling capability.

## Installation

APeB requires Python 3.10 or newer. Create the project environment inside the repository:

```bash
conda create -n apeb python==3.12
conda activate apeb
pip install -e .
```

For development and tests, install `.[test]`.

## Model configuration

Copy `models.example.yaml` to an ignored local path such as `models.local.yaml`. Configuration files may name models and generation parameters, but credentials and custom endpoints must be environment-variable references.

```bash
cp models.example.yaml models.local.yaml
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="..."
```

Model entries may need provider-specific options (for example, "thinking" should be placed in "extra_body", but "reasoning_effort" does not), which differ between providers; consult your provider's documentation when configuring an entry.

Pass the local file with `--model-config`, or set `APEB_MODEL_CONFIG`. A model is selected deterministically with `GROUP/NAME`, for example `BASIC_MODEL/default`; APeB never randomly selects a configured model.

## Dataset

The released dataset is hosted on Hugging Face (`<HF_DATASET_ID>`). Its dataset card documents the task, the file families, the privacy processing, and the fact that `answer` is a 1-based candidate position.

```bash
pip install -U huggingface_hub
mkdir -p data/raw
hf download <HF_DATASET_ID> --repo-type dataset --local-dir data/raw
```

The release package is not the evaluation schema. Convert it once with `apeb convert-release`, which reads `simple_prompt/<...>/<bucket>_prompt.json` for the model input and label and the matching `history_details/<...>/<bucket>_detailed_information.json` for the per-sample resources, so both file families must be downloaded for the buckets you convert. Each converted sample keeps `metadata.release_bucket` and `metadata.release_record_id` so results can be traced back to the package.

```bash
# Everything
apeb convert-release data/raw --output-dir data/evaluation

# Quick subset: one bucket, ten samples
apeb convert-release data/raw --buckets 1016_1020 --limit 10 --output-dir data/mini_evaluation
```

`data/evaluation` holds the full release (14 buckets, 6,242 samples); `data/mini_evaluation` is the ten-sample subset used by the examples below. Both are ordinary `apeb.eval.v1` data and can be passed straight to `apeb evaluate`.

## Dataset format

Every dataset must include `dataset_manifest.json` and use schema version `apeb.eval.v1`. A combined record looks like this:

```json
{
  "schema_version": "apeb.eval.v1",
  "sample_id": "sample_001",
  "task": "predict_order",
  "prompt": "<history>...</history>\n<query>...</query>\n<candidates>...</candidates>",
  "resources": {
    "history": {"history_001": "..."},
    "candidates": {"candidate_001": "..."}
  },
  "answer_indices": [1],
  "metadata": {}
}
```

Two layouts are supported:

- Combined: `samples.jsonl`
- Split: `prompts.jsonl` plus `details.jsonl`, joined by `sample_id`

The manifest records the dataset version, license, representation, and whether the release completed privacy review. `examples/combined` and `examples/split` are synthetic, one-sample fixtures kept only as references for the two layouts; the commands in this README use the converted release data instead. JSON Schemas are under `schemas/`.

Validate data before evaluation:

```bash
apeb validate-data data/mini_evaluation
```

## Evaluation

LLM example, which outputs the recommended product in one response.

```bash
apeb evaluate data/mini_evaluation \
  --framework raw \
  --model BASIC_MODEL/default \
  --model-config models.local.yaml \
  --output-dir outputs/raw-default
```

Agent example, which perform multiple search for the detail information

```bash
apeb evaluate data/mini_evaluation \
  --framework react \
  --model BASIC_MODEL/default \
  --model-config models.local.yaml \
  --tools retriever \
  --output-dir outputs/react-default
```

Safety-sensitive capabilities require two decisions: selecting the tool and passing its gate.

```bash
# Network access
apeb evaluate data/mini_evaluation \
  --framework react \
  --model BASIC_MODEL/default \
  --model-config models.local.yaml \
  --tools retriever web_search crawl \
  --allow-network-tools \
  --output-dir outputs/network-run

# Local Python execution
apeb evaluate data/mini_evaluation \
  --framework deerflow \
  --model BASIC_MODEL/default \
  --model-config models.local.yaml \
  --tools retriever python_repl \
  --allow-code-execution \
  --output-dir outputs/code-run
```

## Outputs and logging

The default output directory contains:

- `summary.json`: aggregate metrics and enabled privacy-sensitive capabilities
- `results.jsonl`: sample ID, ranking indices, ground truth indices, status, and metrics

Prompts, detailed resources, full responses, and agent traces are not written by default. `--save-responses` and `--save-traces` create separate ignored artifacts; treat them as sensitive. Logs contain operational status and failure reasons rather than prompt, tool input/output, model configuration, or response bodies.

Aggregate multiple runs with:

```bash
apeb summarize outputs/raw-default outputs/react-default
```

## Security and privacy

Read [SECURITY.md](SECURITY.md) before enabling external providers, web access, crawling, code execution, or sensitive artifacts.

## Licenses

The source code is released under the MIT License. The benchmark dataset is licensed separately under CC BY-NC-ND 4.0; see [DATASET_LICENSE.md](DATASET_LICENSE.md). The synthetic examples in this repository are provided solely to demonstrate the benchmark format.
