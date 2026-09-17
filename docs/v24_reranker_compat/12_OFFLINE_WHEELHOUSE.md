# Offline Wheelhouse

Status: `MISSING`

Expected local wheelhouse:

```text
D:\EReviewAgent\wheelhouse\transformers451
```

Observed result:

- Directory was created for the attempted download.
- No wheel files were downloaded.
- `pip download transformers==4.51.3` failed with TLS EOF against PyPI.
- Conda cache only contains old Python 3.7-era packages: `transformers-4.24.0`, `tokenizers-0.11.4`, and `huggingface_hub-0.10.1`; these do not satisfy the target matrix.

Required offline acquisition on a trusted network-working Windows machine:

```powershell
python -m pip download `
  --dest D:\wheelhouse\ereview-transformers451 `
  "transformers==4.51.3"

Get-FileHash `
  D:\wheelhouse\ereview-transformers451\* `
  -Algorithm SHA256 |
  Export-Csv `
  D:\wheelhouse\ereview-transformers451\SHA256SUMS.csv `
  -NoTypeInformation
```

Copy the complete directory to:

```text
D:\EReviewAgent\wheelhouse\transformers451
```

The wheelhouse must include `transformers==4.51.3` and its resolved dependencies such as `tokenizers`, `huggingface-hub`, `safetensors`, `packaging`, `filelock`, `regex`, `requests`, `pyyaml`, `tqdm`, and `numpy` as resolved by pip for the target Python/Windows architecture.
