# Package Audit

## Source Package

- Archive: `D:\EReviewAgent\EReview_Transformers451_兼容安装包.zip`
- SHA256: `ADA71BBBDA2870A009C8EFF5CB2397BD5B145B2F2B121273D7577066CC094EF4`

## Extracted Files

- `Install-EReviewTransformers451.ps1`
- `Verify-EReviewTransformers451.ps1`
- `README_安装说明.txt`
- `requirements-transformers451.txt`
- `SHA256SUMS.txt`
- `official_sources.json`

## Script Audit

The install script was reviewed before execution. It only installs:

- `huggingface-hub==0.30.2`
- `tokenizers==0.21.1`
- `transformers==4.51.3`

No commands were found that modify torch, CUDA packages, FlagEmbedding, sentence-transformers, model weights, databases, Git history, or project tests.

## Wheel Hashes

- `huggingface_hub-0.30.2-py3-none-any.whl`: `68FF05969927058CFA41DF4F2155D4BB48F5F54F719DD0390103EEFA9B191E28`
- `tokenizers-0.21.1-cp39-abi3-win_amd64.whl`: `0F0DCBCC9F6E13E675A66D7A5F2F225A736745CE484C1A4E07476A89CCDAD382`
- `transformers-4.51.3-py3-none-any.whl`: `FD3279633CEB2B777013234BBF0B4F5C2D23C4626B05497691F00CFDA55E8A83`
