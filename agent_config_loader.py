#!/usr/bin/env python3
"""
Agent Config Loader

config.json 파일에서 에이전트별 모델 설정을 로드하고 LLM 인스턴스를 생성한다.

지원 provider:
  - openai     : ChatOpenAI (OpenAI 및 OpenAI 호환 API - KISTI, LiteLLM 등)
  - anthropic  : ChatAnthropic (Claude 계열)
  - google     : ChatGoogleGenerativeAI (Gemini 계열)

config.json 예시:
  OpenAI 호환:
    { "provider": "openai", "model": "kistillm",
      "base_url": "https://...", "api_key": "dummy" }

  Anthropic:
    { "provider": "anthropic", "model": "claude-sonnet-4-6",
      "api_key": "sk-ant-..." }

  Google:
    { "provider": "google", "model": "gemini-2.0-flash",
      "api_key": "AIza..." }

provider 생략 시 "openai"로 간주 (하위 호환).
api_key 생략 시 환경변수 (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY) 사용.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("openai", "anthropic", "google")


# ── 기본 설정 ────────────────────────────────────────────────────────────────

def _get_default_config() -> Dict[str, Any]:
    """
    기본 설정값 (OpenAI 호환 - 하위 호환성 유지).

    우선순위: config.json > 환경변수 > 하드코딩 기본값
    """
    return {
        "provider": "openai",
        "model": os.environ.get("KISTI_MODEL", "kistillm"),
        "base_url": os.environ.get("OPENAI_API_BASE", "https://aida.kisti.re.kr:10411/v1"),
        "api_key": os.environ.get("OPENAI_API_KEY", "dummy"),
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.7")),
        "max_tokens": None,
        "timeout": int(os.environ.get("LLM_TIMEOUT", "120")),
        "max_retries": 2,
    }


# ── 설정 로드 ────────────────────────────────────────────────────────────────

def load_agent_config(config_path: str) -> Dict[str, Any]:
    """
    config.json 파일에서 에이전트 설정 로드.

    Args:
        config_path: config.json 파일 경로

    Returns:
        설정 딕셔너리 (기본값 + 파일값 병합)
    """
    config_file = Path(config_path)

    # provider가 openai가 아니면 기본값을 그대로 쓰면 안 되므로,
    # 파일을 먼저 읽어 provider를 확인한 뒤 기본값을 결정한다.
    if not config_file.exists():
        logger.info(f"config.json 없음: {config_path} (기본값 사용)")
        return _get_default_config()

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            file_config = json.load(f)

        provider = file_config.get("provider", "openai").lower()

        # OpenAI 호환만 openai 기본값을 base로 사용; 다른 provider는 빈 dict 시작
        if provider == "openai":
            config = _get_default_config()
        else:
            config = {"provider": provider, "max_retries": 2}

        config.update(file_config)

        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"지원하지 않는 provider: {provider!r}. "
                f"지원 목록: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        logger.info(
            f"config.json 로드: provider={config['provider']}, model={config['model']}"
        )
        return config

    except (ValueError, KeyError) as e:
        logger.error(f"config.json 설정 오류: {e}")
        raise
    except Exception as e:
        logger.error(f"config.json 로드 실패: {e} (기본값 사용)")
        return _get_default_config()


# ── Provider별 모델 생성 ─────────────────────────────────────────────────────

def _create_openai_model(config: Dict[str, Any]):
    """ChatOpenAI 생성 (OpenAI 및 OpenAI 호환 API)."""
    from langchain_openai import ChatOpenAI

    api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY", "dummy")

    kwargs: Dict[str, Any] = {
        "model": config["model"],
        "api_key": api_key,
        "timeout": config.get("timeout", 120),
        "max_retries": config.get("max_retries", 2),
    }

    if config.get("base_url"):
        kwargs["base_url"] = config["base_url"]

    if config.get("temperature") is not None:
        kwargs["temperature"] = config["temperature"]

    if config.get("max_tokens") is not None:
        kwargs["max_tokens"] = config["max_tokens"]

    for param in ("top_p", "frequency_penalty", "presence_penalty", "streaming", "n", "stop"):
        if config.get(param) is not None:
            kwargs[param] = config[param]

    return ChatOpenAI(**kwargs)


def _create_anthropic_model(config: Dict[str, Any]):
    """ChatAnthropic 생성 (Claude 계열)."""
    from langchain_anthropic import ChatAnthropic

    api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Anthropic API 키 필요: config.json의 api_key 또는 "
            "ANTHROPIC_API_KEY 환경변수를 설정하세요."
        )

    kwargs: Dict[str, Any] = {
        "model": config["model"],
        "api_key": api_key,
        "max_retries": config.get("max_retries", 2),
    }

    if config.get("temperature") is not None:
        kwargs["temperature"] = config["temperature"]

    # Anthropic은 max_tokens가 필수 (미지정 시 모델 기본값 사용)
    if config.get("max_tokens") is not None:
        kwargs["max_tokens"] = config["max_tokens"]

    if config.get("timeout") is not None:
        kwargs["timeout"] = config["timeout"]

    # 프록시 등 커스텀 base_url 지원
    if config.get("base_url"):
        kwargs["base_url"] = config["base_url"]

    return ChatAnthropic(**kwargs)


def _create_google_model(config: Dict[str, Any]):
    """ChatGoogleGenerativeAI 생성 (Gemini 계열)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "Google API 키 필요: config.json의 api_key 또는 "
            "GOOGLE_API_KEY 환경변수를 설정하세요."
        )

    kwargs: Dict[str, Any] = {
        "model": config["model"],
        "google_api_key": api_key,
    }

    if config.get("temperature") is not None:
        kwargs["temperature"] = config["temperature"]

    # Google은 max_output_tokens 파라미터명 사용
    if config.get("max_tokens") is not None:
        kwargs["max_output_tokens"] = config["max_tokens"]

    if config.get("max_retries") is not None:
        kwargs["max_retries"] = config["max_retries"]

    return ChatGoogleGenerativeAI(**kwargs)


# ── 공개 API ─────────────────────────────────────────────────────────────────

def create_model_from_config(config: Dict[str, Any]):
    """
    설정 딕셔너리에서 LLM 인스턴스 생성.

    config["provider"] 에 따라 ChatOpenAI / ChatAnthropic /
    ChatGoogleGenerativeAI 중 하나를 반환한다.

    Args:
        config: load_agent_config()가 반환한 설정 딕셔너리

    Returns:
        LangChain BaseChatModel 인스턴스
    """
    provider = config.get("provider", "openai").lower()

    _factory = {
        "openai": _create_openai_model,
        "anthropic": _create_anthropic_model,
        "google": _create_google_model,
    }

    if provider not in _factory:
        raise ValueError(
            f"지원하지 않는 provider: {provider!r}. "
            f"지원 목록: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    model = _factory[provider](config)
    logger.info(f"모델 생성 완료: provider={provider}, model={config['model']}")
    return model


def load_model_from_config_file(config_path: str):
    """
    config.json 파일에서 직접 모델 생성 (편의 함수).

    Args:
        config_path: config.json 파일 경로

    Returns:
        LangChain BaseChatModel 인스턴스
    """
    config = load_agent_config(config_path)
    return create_model_from_config(config)


# ── 테스트 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Agent Config Loader 테스트")
    print("=" * 60)

    test_cases = [
        {
            "label": "OpenAI 호환 (KISTI)",
            "config": {
                "provider": "openai",
                "model": "kistillm",
                "base_url": "https://aida.kisti.re.kr:10411/v1",
                "api_key": "dummy",
                "temperature": 0.5,
                "max_tokens": 4096,
            },
        },
        {
            "label": "Anthropic (Claude)",
            "config": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
                "temperature": 0.5,
                "max_tokens": 4096,
            },
        },
        {
            "label": "Google (Gemini)",
            "config": {
                "provider": "google",
                "model": "gemini-2.0-flash",
                "api_key": os.environ.get("GOOGLE_API_KEY", ""),
                "temperature": 0.5,
                "max_tokens": 4096,
            },
        },
    ]

    for tc in test_cases:
        print(f"\n[{tc['label']}]")
        cfg = tc["config"]
        if not cfg.get("api_key"):
            print(f"  SKIP: api_key 없음 (환경변수 미설정)")
            continue
        try:
            model = create_model_from_config(cfg)
            print(f"  OK: {type(model).__name__}")
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)

    print("\n완료!")
