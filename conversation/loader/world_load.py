from pathlib import Path
from typing import Optional

import yaml
from loguru import logger


def load_world(yaml_path: str | Path) -> dict:
    """W_*.yaml 파일을 로드해 dict를 반환한다."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"세계관 파일 없음: {path}")

    with open(path, encoding="utf-8") as f:
        data: dict = yaml.safe_load(f)

    return data


def get_act(world: dict, scenario_id: str, act_id: str) -> Optional[dict]:
    """world dict에서 특정 scenario + act를 찾아 반환한다. 없으면 None."""
    for scenario in world.get("scenarios", []):
        if scenario.get("scenario_id") == scenario_id:
            for act in scenario.get("acts", []):
                if act.get("act_id") == act_id:
                    return act
    logger.warning(f"[world_load] act 없음: scenario={scenario_id}, act={act_id}")
    return None
