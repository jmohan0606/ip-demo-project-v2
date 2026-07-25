"""Round 13 verification — cdao GPT-5 compatibility (FIX_SPEC_R13 F).

Fixtures only (no real cdao here): a fake `cdao` module captures the kwargs of
`openai_azure_client(...)` and of every `.chat.completions.create(...)`, so the
checks assert the ACTUAL construction and call kwargs for the main LLM and all
three roles:

  [1] empty api_version  -> constructed with workspace_id ONLY (no api_version arg)
  [2] non-empty          -> api_version passed exactly as before (GPT-4 path)
  [3] every chat-completions create passes temperature (default 1) and NO
      max_tokens — main + writer + judge + assistant (+ real-mode adapter)
  [4] the Anthropic adapter still sends max_tokens=1024 (unchanged)
  [5] the per-role Env Health probe runs the corrected construction + a minimal
      create on cdao (same code path as runtime)
  [6] all-empty per-role config still behaves as R12 (roles unconfigured;
      temperature defaults to 1.0 and never counts as R12 config)

Run: python scripts/verify_gpt5_compat.py  (exit 0 = ALL PASS)
"""
from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


class _FakeCompletions:
    def __init__(self, log: list):
        self._log = log

    def create(self, **kwargs):
        self._log.append(kwargs)
        msg = types.SimpleNamespace(content="OK")
        choice = types.SimpleNamespace(message=msg)
        usage = types.SimpleNamespace(prompt_tokens=1, completion_tokens=1)
        return types.SimpleNamespace(choices=[choice], usage=usage)


class _FakeCdaoClient:
    def __init__(self, create_log: list):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(create_log))


def install_fake_cdao() -> tuple[list, list]:
    """Install a fake `cdao` module; returns (construction_kwargs, create_kwargs) logs."""
    ctor_log: list = []
    create_log: list = []
    fake = types.ModuleType("cdao")

    def openai_azure_client(**kwargs):
        ctor_log.append(kwargs)
        return _FakeCdaoClient(create_log)

    fake.openai_azure_client = openai_azure_client
    sys.modules["cdao"] = fake
    return ctor_log, create_log


def fresh_settings(**env):
    """Rebuild Settings from a controlled env (cdao mode, fake workspace)."""
    base = {
        "LLM_CLIENT_MODE": "cdao_openai",
        "CDAO_WORKSPACE_ID": "ws-test",
        "CDAO_MODEL": "test-model",
    }
    base.update(env)
    for key in list(os.environ):
        if key.startswith(("CDAO_", "WRITER_", "JUDGE_", "ASSISTANT_", "LLM_CLIENT_MODE")):
            del os.environ[key]
    os.environ.update({k: v for k, v in base.items() if v is not None})
    from app.config import settings as settings_mod
    settings_mod.get_settings.cache_clear()
    return settings_mod.get_settings()


def main() -> int:
    ctor_log, create_log = install_fake_cdao()

    print("[1] empty api_version -> workspace_id only (no api_version arg)")
    from app.llm.client import build_cdao_openai_client
    for empty in ("", None, "   "):
        ctor_log.clear()
        build_cdao_openai_client(empty, "ws-test")
        check(f"api_version={empty!r} omitted", ctor_log == [{"workspace_id": "ws-test"}],
              str(ctor_log))

    print("[2] non-empty api_version -> passed exactly as before (GPT-4 path)")
    ctor_log.clear()
    build_cdao_openai_client("2024-02-01", "ws-test")
    check("api_version passed",
          ctor_log == [{"api_version": "2024-02-01", "workspace_id": "ws-test"}], str(ctor_log))

    print("[3] every cdao create: temperature present (default 1), NO max_tokens")
    settings = fresh_settings(CDAO_API_VERSION="")  # GPT-5-style: omit api_version
    import app.llm.client as client_mod
    client_mod.reset_llm_client()

    # main LLM
    ctor_log.clear(); create_log.clear()
    main_llm = client_mod.get_llm_client()
    main_llm.generate("ping")
    check("main: constructed workspace_id-only", ctor_log == [{"workspace_id": "ws-test"}],
          str(ctor_log))
    check("main: temperature=1.0, no max_tokens",
          len(create_log) == 1 and create_log[0].get("temperature") == 1.0
          and "max_tokens" not in create_log[0], str(create_log))

    # three roles — configured on cdao with empty api_version
    from app.llm.roles import build_configured_role_client, resolve_role_config
    for role in ("writer", "judge", "assistant"):
        settings = fresh_settings(
            CDAO_API_VERSION="",
            **{f"{role.upper()}_CLIENT_MODE" if role != "assistant" else "ASSISTANT_LLM_MODE": "cdao_openai",
               f"{role.upper()}_DEPLOYMENT": f"{role}-gpt5"},
        )
        cfg = resolve_role_config(role, settings)
        check(f"{role}: R12-configured for the test", cfg.configured, str(cfg))
        ctor_log.clear(); create_log.clear()
        role_client = build_configured_role_client(cfg)
        role_client.generate("ping")
        check(f"{role}: constructed workspace_id-only",
              ctor_log == [{"workspace_id": "ws-test"}], str(ctor_log))
        check(f"{role}: temperature=1.0, no max_tokens, routed to deployment",
              len(create_log) == 1 and create_log[0].get("temperature") == 1.0
              and "max_tokens" not in create_log[0]
              and create_log[0].get("model") == f"{role}-gpt5", str(create_log))

    # per-role temperature override reaches the create
    settings = fresh_settings(CDAO_API_VERSION="", JUDGE_CLIENT_MODE="cdao_openai",
                              JUDGE_DEPLOYMENT="judge-gpt4", JUDGE_TEMPERATURE="0.2")
    cfg = resolve_role_config("judge", settings)
    ctor_log.clear(); create_log.clear()
    build_configured_role_client(cfg).generate("ping")
    check("judge: JUDGE_TEMPERATURE=0.2 reaches the create",
          create_log and create_log[0].get("temperature") == 0.2, str(create_log))

    # real-mode adapter (the other chat-completions path) — fake AzureOpenAI
    real_create_log: list = []
    fake_openai = types.ModuleType("openai")

    class _FakeAzureOpenAI:  # noqa: D401
        def __init__(self, **kwargs):
            self.chat = types.SimpleNamespace(completions=_FakeCompletions(real_create_log))

    fake_openai.AzureOpenAI = _FakeAzureOpenAI
    had_openai = sys.modules.get("openai")
    sys.modules["openai"] = fake_openai
    try:
        settings = fresh_settings(LLM_CLIENT_MODE="real",
                                  AZURE_OPENAI_ENDPOINT="https://x", AZURE_OPENAI_API_KEY="k",
                                  AZURE_OPENAI_DEPLOYMENT="dep")
        client_mod.build_llm_client("real").generate("ping")
        check("real-mode adapter: temperature=1.0, no max_tokens",
              real_create_log and real_create_log[0].get("temperature") == 1.0
              and "max_tokens" not in real_create_log[0], str(real_create_log))
    finally:
        if had_openai is not None:
            sys.modules["openai"] = had_openai
        else:
            del sys.modules["openai"]
        for key in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"):
            os.environ.pop(key, None)

    print("[4] Anthropic adapter still sends max_tokens (unchanged)")
    import inspect
    src = inspect.getsource(client_mod.ClaudeLLMClient.generate)
    check("ClaudeLLMClient.generate carries max_tokens=1024", "max_tokens=1024" in src)
    src_all = inspect.getsource(client_mod)
    check("no other max_tokens in app/llm/client.py",
          src_all.count("max_tokens=1024") == 1)

    print("[5] Env Health per-role probe uses the corrected path (minimal create on cdao)")
    settings = fresh_settings(CDAO_API_VERSION="", WRITER_CLIENT_MODE="cdao_openai",
                              WRITER_DEPLOYMENT="writer-gpt5")
    from app.services.llm_connectivity import _cheap_check
    cfg = resolve_role_config("writer", settings)
    ctor_log.clear(); create_log.clear()
    row = _cheap_check(cfg)
    check("probe: constructed workspace_id-only", ctor_log == [{"workspace_id": "ws-test"}],
          str(ctor_log))
    check("probe: minimal create — temperature=1.0, no max_tokens, one call",
          len(create_log) == 1 and create_log[0].get("temperature") == 1.0
          and "max_tokens" not in create_log[0], str(create_log))
    check("probe: status model-found via corrected runtime path",
          row.get("status") == "model-found" and "corrected runtime path" in row.get("check", ""),
          str(row))

    print("[6] all-empty per-role config still behaves as R12; temperature defaults to 1")
    settings = fresh_settings(CDAO_API_VERSION="2024-02-01")
    from app.llm.roles import build_role_llm
    for role in ("writer", "judge", "assistant"):
        cfg = resolve_role_config(role, settings)
        check(f"{role}: unconfigured (no R12 keys)", not cfg.configured, str(cfg))
        check(f"{role}: temperature defaults to 1.0", cfg.temperature == 1.0, str(cfg))
        check(f"{role}: build_role_llm -> None (pre-R12 path kept)",
              build_role_llm(role, settings) is None)
    # JUDGE_MODEL alone / ASSISTANT_LLM_MODE alone stay non-R12 (regression guard)
    settings = fresh_settings(CDAO_API_VERSION="2024-02-01", JUDGE_MODEL="gpt-x",
                              ASSISTANT_LLM_MODE="cdao_openai")
    check("JUDGE_MODEL alone stays non-R12",
          not resolve_role_config("judge", settings).configured)
    check("ASSISTANT_LLM_MODE alone stays non-R12",
          not resolve_role_config("assistant", settings).configured)
    # non-empty api_version still constructs WITH api_version through a role
    settings = fresh_settings(CDAO_API_VERSION="", JUDGE_CLIENT_MODE="cdao_openai",
                              JUDGE_DEPLOYMENT="judge-gpt4",
                              JUDGE_API_VERSION="2024-06-01")
    ctor_log.clear()
    build_configured_role_client(resolve_role_config("judge", settings))
    check("role api_version set -> passed to construction",
          ctor_log == [{"api_version": "2024-06-01", "workspace_id": "ws-test"}], str(ctor_log))

    # restore a clean settings cache for anything run after this script
    fresh_settings(CDAO_API_VERSION="2024-02-01")
    print(f"\n{'ALL PASS' if FAIL == 0 else 'FAILURES'}: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
