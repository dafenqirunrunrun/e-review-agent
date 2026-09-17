# v1.6.1.4 VLM Device Placement Comparison

## Conclusion

Selected mode: `auto`

## Comparison

```json
[
  {
    "mode": "auto",
    "attempts": [
      {
        "error_code": "DEVICE_PLACEMENT_TIMEOUT",
        "error_summary": "timeout after 600s"
      }
    ],
    "metrics": {
      "oom": false,
      "output_schema_valid": false,
      "timeout": true
    }
  },
  {
    "mode": "cuda",
    "attempts": [
      {
        "error_code": "DEVICE_PLACEMENT_TIMEOUT",
        "error_summary": "timeout after 600s"
      }
    ],
    "metrics": {
      "oom": false,
      "output_schema_valid": false,
      "timeout": true
    }
  }
]
```

## Selection Rule

The selected mode must avoid OOM, keep schema output valid, preserve at least
400 MB of GPU memory safety margin, and prefer the faster generate path only
when stability is preserved.
