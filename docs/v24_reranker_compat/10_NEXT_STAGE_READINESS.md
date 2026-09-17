# Next Stage Readiness

Current readiness: `BLOCKED_ON_OFFLINE_WHEEL`

Required next input:

```text
FlagEmbedding==1.4.0 wheel or source distribution compatible with Python 3.10
```

Suggested offline acquisition on a network-working machine:

```powershell
py -3.10 -m pip download --no-deps -d D:\wheelhouse FlagEmbedding==1.4.0
```

Copy the resulting file to the target machine, then run:

```powershell
D:\anaconda\envs\ereview-v24-reranker-fix\python.exe -m pip install --no-index --no-deps D:\wheelhouse\FlagEmbedding-1.4.0-py3-none-any.whl
```

Then execute:

1. `pip check`
2. Import smoke
3. Formal reranker runtime test
4. Phase 3B formal gate
5. Qwen regression
6. v2.4 trace/replay regression
7. Python full suite
8. Dependency lock update if all gates pass

Do not change `torchtest`, `D:\EReviewAgent\litemall-v24-canonical`, model files, database files, or original branch state.
