# Security and privacy

## Reporting a vulnerability

Please use the repository host's private security-advisory channel. Do not include credentials, private dataset rows, prompts, traces, or model responses in a public issue.

## Credentials

- Keep credentials in environment variables.
- Keep custom service endpoints in environment variables.
- Use `models.example.yaml` only as a template and store local copies under an ignored name such as `models.local.yaml`.
- APeB resolves only exact `${NAME}` references and fails when a referenced variable is missing.
- Model configuration values are never logged.

If a credential may have been committed or printed, revoke it at the provider and replace it. Removing it from the latest file is not sufficient for an already published Git history.

## Dataset privacy boundary

APeB evaluates already reviewed, de-identified or pseudonymized data. It does not claim that pseudonymization is encryption, and this release does not provide a raw-data transformation pipeline.

Every dataset requires a manifest. Evaluation stops when `privacy_reviewed` is false unless the operator explicitly accepts the risk.

## External effects

- Local structured retrieval is the default.
- Web search and crawling require `--allow-network-tools`.
- Python execution requires `--allow-code-execution`.
- External LLM providers receive the model input needed by the selected method. Review provider retention and training policies before use.

Run experiments in an isolated environment when enabling code execution or tools that consume untrusted web content.