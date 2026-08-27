import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from .cipher_workbench import CipherWorkbench
from .config import load_env_local
from .domain import PuzzleInput
from .providers.deepseek import DeepSeekConfig, DeepSeekProvider
from .solver import OfflineProvider, PuzzleSolver


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="puzzle-agent", description="CLI puzzle-solving agent")
    commands = parser.add_subparsers(dest="command", required=True)

    solve = commands.add_parser("solve", help="Solve a puzzle from a JSON file")
    solve.add_argument("--file", required=True, type=Path)
    solve.add_argument("--offline", action="store_true", help="Use deterministic local analysis without network")
    solve.add_argument("--key", action="append", default=[], help="Candidate Vigenere key; repeatable")
    solve.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"))

    ciphers = commands.add_parser("ciphers", help="Run the local cipher workbench")
    ciphers.add_argument("--text", required=True)
    ciphers.add_argument("--key", action="append", default=[])
    ciphers.add_argument("--limit", type=int, default=20)

    session = commands.add_parser("session", help="Manage a persistent complex puzzle session")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    init = session_commands.add_parser("init", help="Create a complex puzzle session")
    init.add_argument("--file", required=True, type=Path)
    init.add_argument("--max-calls", type=int, default=6)
    init.add_argument("--sessions-root", type=Path, default=Path(".puzzle-agent/sessions"))

    for name in ("run", "step", "status", "history"):
        command = session_commands.add_parser(name)
        command.add_argument("session_id")
        command.add_argument("--sessions-root", type=Path, default=Path(".puzzle-agent/sessions"))
        if name in {"run", "step"}:
            command.add_argument("--offline", action="store_true")
            command.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"))
    add_artifact = session_commands.add_parser("add-artifact")
    add_artifact.add_argument("session_id")
    add_artifact.add_argument("--name", required=True)
    add_artifact.add_argument("--file", required=True, type=Path)
    add_artifact.add_argument("--offline", action="store_true")
    add_artifact.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"))
    add_artifact.add_argument("--sessions-root", type=Path, default=Path(".puzzle-agent/sessions"))
    branch = session_commands.add_parser("branch")
    branch.add_argument("session_id")
    branch.add_argument("--checkpoint", required=True)
    branch.add_argument("--sessions-root", type=Path, default=Path(".puzzle-agent/sessions"))
    finalize = session_commands.add_parser("finalize")
    finalize.add_argument("session_id")
    finalize.add_argument("--sessions-root", type=Path, default=Path(".puzzle-agent/sessions"))

    benchmark = commands.add_parser("benchmark", help="Validate or run derived benchmark suites")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    validate = benchmark_commands.add_parser("validate")
    validate.add_argument("--root", type=Path, default=Path("benchmarks/derived"))
    validate.add_argument("--suite", choices=("dev", "blind"), default="dev")
    benchmark_run = benchmark_commands.add_parser("run")
    benchmark_run.add_argument("--root", type=Path, default=Path("benchmarks/derived"))
    benchmark_run.add_argument("--suite", choices=("dev", "blind"), default="dev")
    benchmark_run.add_argument("--provider", choices=("offline", "deepseek"), default="offline")
    benchmark_run.add_argument("--max-calls", type=int, default=6)
    benchmark_run.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"))
    benchmark_run.add_argument(
        "--sessions-root", type=Path, default=Path(".puzzle-agent/benchmark-sessions")
    )
    return parser


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    load_env_local()
    args = _parser().parse_args(argv)
    try:
        if args.command == "ciphers":
            if args.limit < 1:
                raise ValueError("--limit must be at least 1")
            candidates = CipherWorkbench(max_candidates=args.limit).analyze(
                PuzzleInput(content=args.text), tuple(args.key)
            )
            _print_json([asdict(candidate) for candidate in candidates])
            return 0

        if args.command == "benchmark":
            from .benchmark import discover_cases, evaluate_case, load_runtime_input, validate_case
            cases = discover_cases(args.root, args.suite)
            validations = [
                {"case": case.name, "errors": validate_case(case)} for case in cases
            ]
            if args.benchmark_command == "validate":
                _print_json({
                    "suite": args.suite,
                    "total": len(cases),
                    "invalid": sum(bool(item["errors"]) for item in validations),
                    "cases": validations,
                })
                return 0 if cases and not any(item["errors"] for item in validations) else 2
            if not cases or any(item["errors"] for item in validations):
                raise ValueError("Benchmark suite is empty or contains invalid cases")
            try:
                from .complex_session import SessionManager
            except ModuleNotFoundError as exc:
                if exc.name and exc.name.startswith("langgraph"):
                    raise RuntimeError(
                        'Benchmark run requires: pip install -e ".[complex]"'
                    ) from exc
                raise
            if args.provider == "offline":
                from .complex_offline import OfflineStageProvider
                provider = OfflineStageProvider()
            else:
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    print("DEEPSEEK_API_KEY is required for --provider deepseek.", file=sys.stderr)
                    return 2
                provider = DeepSeekProvider(DeepSeekConfig(
                    api_key=api_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    model=args.model,
                ))
            manager = SessionManager(args.sessions_root)
            results = []
            for case in cases:
                runtime_input = load_runtime_input(case)
                session_id = manager.create(
                    PuzzleInput.from_dict(runtime_input),
                    max_calls=args.max_calls,
                    required_artifacts=tuple(runtime_input.get("required_artifacts", [])),
                    artifacts=runtime_input.get("artifacts", {}),
                )
                state = manager.run(session_id, provider)
                score = evaluate_case(case, state)
                results.append({
                    "case": case.name,
                    "session_id": session_id,
                    "status": state.get("status"),
                    "correct": score["correct"],
                    "calls_used": state.get("budget", {}).get("calls_used", 0),
                })
            _print_json({
                "suite": args.suite,
                "provider": args.provider,
                "total": len(results),
                "correct": sum(item["correct"] for item in results),
                "cases": results,
            })
            return 0

        if args.command == "session":
            try:
                from .complex_session import SessionManager
            except ModuleNotFoundError as exc:
                if exc.name and exc.name.startswith("langgraph"):
                    raise RuntimeError(
                        'Complex sessions require: pip install -e ".[complex]"'
                    ) from exc
                raise
            manager = SessionManager(args.sessions_root)
            if args.session_command == "init":
                data = json.loads(args.file.read_text(encoding="utf-8"))
                puzzle = PuzzleInput.from_dict(data)
                session_id = manager.create(
                    puzzle,
                    max_calls=args.max_calls,
                    required_artifacts=tuple(data.get("required_artifacts", [])),
                    artifacts=data.get("artifacts", {}),
                )
                _print_json({"session_id": session_id})
                return 0
            if args.session_command == "status":
                _print_json(manager.status(args.session_id))
                return 0
            if args.session_command == "history":
                _print_json(manager.history(args.session_id))
                return 0
            if args.session_command == "branch":
                _print_json({
                    "session_id": manager.branch(args.session_id, args.checkpoint),
                    "branched_from": args.session_id,
                })
                return 0
            if args.session_command == "finalize":
                _print_json(manager.finalize(args.session_id))
                return 0

            if args.offline:
                from .complex_offline import OfflineStageProvider
                provider = OfflineStageProvider()
            else:
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    print("DEEPSEEK_API_KEY is required unless --offline is used.", file=sys.stderr)
                    return 2
                provider = DeepSeekProvider(DeepSeekConfig(
                    api_key=api_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    model=args.model,
                ))
            if args.session_command == "run":
                result = manager.run(args.session_id, provider)
            elif args.session_command == "step":
                result = manager.step(args.session_id, provider)
            else:
                result = manager.resume(
                    args.session_id,
                    provider,
                    {args.name: args.file.read_text(encoding="utf-8")},
                )
            _print_json(result)
            return 0

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not args.offline and not api_key:
            print("DEEPSEEK_API_KEY is required unless --offline is used.", file=sys.stderr)
            return 2
        data = json.loads(args.file.read_text(encoding="utf-8"))
        puzzle = PuzzleInput.from_dict(data)
        if args.offline:
            provider = OfflineProvider()
        else:
            provider = DeepSeekProvider(DeepSeekConfig(
                api_key=api_key or "",
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                model=args.model,
            ))
        result = PuzzleSolver(provider).solve(puzzle, tuple(args.key))
        _print_json(asdict(result))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
