from pathlib import Path
from typing import Iterable, List


def validate_local_images(paths: Iterable[str], max_images: int) -> List[Path]:
    output = []
    for value in list(paths or [])[:max_images]:
        path = Path(value)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("VLM_IMAGE_NOT_AVAILABLE")
        output.append(path)
    return output
