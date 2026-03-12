#!/usr/bin/env python3
"""
Agent Config Loader

config.json 파일에서 에이전트별 모델 설정을 로드
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def _get_default_config() -> Dict[str, Any]:
    """
    기본 설정값 (환경변수 우선, 없으면 하드코딩 fallback)

    우선순위: config.json > 환경변수 > 하드코딩 기본값
    """
    return {
        "model": os.environ.get("KISTI_MODEL", "kistillm"),
        "base_url": os.environ.get("OPENAI_API_BASE", "https://aida.kisti.re.kr:10411/v1"),
        "api_key": os.environ.get("OPENAI_API_KEY", "dummy"),
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.7")),
        "max_tokens": None,
        "timeout": int(os.environ.get("LLM_TIMEOUT", "120")),
        "max_retries": 2,
    }


def load_agent_config(config_path: str) -> Dict[str, Any]:
    """
    config.json 파일에서 에이전트 설정 로드

    Args:
        config_path: config.json 파일 경로

    Returns:
        설정 딕셔너리 (기본값 + 파일값 병합)
    """
    config_file = Path(config_path)

    # 기본 설정으로 시작 (환경변수 반영)
    config = _get_default_config()

    if not config_file.exists():
        logger.info(f"config.json 없음: {config_path} (기본값 사용)")
        return config

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            file_config = json.load(f)

        # 파일 설정으로 업데이트 (덮어쓰기)
        config.update(file_config)

        logger.info(f"config.json 로드: {config['model']} @ {config['base_url']}")

        return config

    except Exception as e:
        logger.error(f"config.json 로드 실패: {e} (기본값 사용)")
        return _get_default_config()


def create_model_from_config(config: Dict[str, Any]) -> ChatOpenAI:
    """
    설정에서 ChatOpenAI 모델 생성

    Args:
        config: 에이전트 설정 딕셔너리

    Returns:
        ChatOpenAI 인스턴스
    """
    # ChatOpenAI 파라미터 준비
    model_kwargs = {
        "model": config["model"],
        "base_url": config["base_url"],
        "api_key": config["api_key"],
        "timeout": config["timeout"],
        "max_retries": config["max_retries"],
    }

    # temperature 추가 (선택사항)
    if "temperature" in config and config["temperature"] is not None:
        model_kwargs["temperature"] = config["temperature"]

    # max_tokens 추가 (선택사항)
    if "max_tokens" in config and config["max_tokens"] is not None:
        model_kwargs["max_tokens"] = config["max_tokens"]

    # 추가 파라미터 (있으면)
    optional_params = [
        "top_p", "frequency_penalty", "presence_penalty",
        "streaming", "n", "stop"
    ]

    for param in optional_params:
        if param in config and config[param] is not None:
            model_kwargs[param] = config[param]

    return ChatOpenAI(**model_kwargs)


def load_model_from_config_file(config_path: str) -> ChatOpenAI:
    """
    config.json 파일에서 직접 모델 생성 (편의 함수)

    Args:
        config_path: config.json 파일 경로

    Returns:
        ChatOpenAI 인스턴스
    """
    config = load_agent_config(config_path)
    return create_model_from_config(config)


if __name__ == "__main__":
    # 테스트
    print("=" * 60)
    print("Agent Config Loader 테스트")
    print("=" * 60)

    # 예제 config.json 생성
    test_config = {
        "model": "gpt-4",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
        "temperature": 0.5,
        "max_tokens": 2048,
        "timeout": 60,
    }

    with open("test_config.json", "w") as f:
        json.dump(test_config, f, indent=2)

    print("\n📝 test_config.json 생성:")
    print(json.dumps(test_config, indent=2))

    print("\n" + "=" * 60)
    print("설정 로드 테스트")
    print("=" * 60)

    # 설정 로드
    config = load_agent_config("test_config.json")

    print("\n로드된 설정:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("모델 생성 테스트")
    print("=" * 60)

    # 모델 생성
    model = create_model_from_config(config)

    print(f"\n✅ 모델 생성 완료:")
    print(f"  타입: {type(model)}")
    print(f"  모델명: {model.model_name}")
    print(f"  Base URL: {model.openai_api_base}")

    print("\n" + "=" * 60)
    print("파일 없을 때 테스트 (기본값)")
    print("=" * 60)

    config_default = load_agent_config("nonexistent.json")

    print("\n기본 설정:")
    for key, value in config_default.items():
        print(f"  {key}: {value}")

    print("\n✅ 모든 테스트 완료!")
