"""buem – command-line interface.

Console entry-point declared in pyproject.toml::

    [project.scripts]
    buem = "buem.cli:main"

Subcommands
-----------
buem run            Run the ISO 52016 thermal model for a single building.
buem api            Start the BUEM REST API server (Gunicorn or Flask dev).
buem validate       Verify the installation and environment paths.
buem multibuilding  Run parallel multi-building processing.
"""
from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="buem",
        description="Building Urban Energy Model (BUEM) — ISO 52016 5R1C thermal model",
    )
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    # ── run ──────────────────────────────────────────────────────────────────
    run_p = sub.add_parser(
        "run",
        help="Run the thermal model for a single building",
    )
    run_p.add_argument("--plot", action="store_true", help="Generate result plots")
    run_p.add_argument(
        "--milp", action="store_true", help="Use MILP solver (experimental)"
    )

    # ── api ──────────────────────────────────────────────────────────────────
    api_p = sub.add_parser("api", help="Start the BUEM REST API server")
    api_p.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    api_p.add_argument(
        "--port", type=int, default=5000, help="Bind port (default: 5000)"
    )
    api_p.add_argument(
        "--workers", type=int, default=2, help="Gunicorn worker processes (default: 2)"
    )
    api_p.add_argument(
        "--dev",
        action="store_true",
        help="Run Flask development server instead of Gunicorn (not for production)",
    )

    # ── validate ─────────────────────────────────────────────────────────────
    sub.add_parser("validate", help="Verify the installation and environment")

    # ── multibuilding ─────────────────────────────────────────────────────────
    mb_p = sub.add_parser(
        "multibuilding", help="Run parallel multi-building processing"
    )
    mb_p.add_argument(
        "--buildings",
        type=int,
        default=4,
        help="Number of buildings to process (default: 4)",
    )
    mb_p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Worker processes (default: auto-detect from CPU count)",
    )
    mb_p.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential processing (disables parallelism)",
    )

    return p


def main() -> None:
    from buem.env import load_env

    load_env()

    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # ── run ──────────────────────────────────────────────────────────────────
    if args.command == "run":
        import numpy as np

        from buem.config.cfg_attribute import cfg
        from buem.main import run_model

        res = run_model(cfg, plot=args.plot, use_milp=args.milp, return_models=True)
        print(f"Heating load total:               {res['heating'].sum():.1f} kWh/yr")
        print(f"Cooling load total:               {res['cooling'].sum():.1f} kWh/yr")
        print(f"Total HVAC (heating + |cooling|): {float(np.sum(res['heating']) + np.sum(np.abs(res['cooling']))):.1f} kWh/yr")
        print(f"Execution time:                   {res['elapsed_s']:.2f} s")

    # ── api ──────────────────────────────────────────────────────────────────
    elif args.command == "api":
        if args.dev:
            from buem.apis.api_server import create_app

            app = create_app()
            print(f"Starting Flask dev server on http://{args.host}:{args.port}")
            print("WARNING: Do not use the development server in production.")
            app.run(host=args.host, port=args.port, debug=False)
        else:
            import subprocess

            cmd = [
                sys.executable, "-m", "gunicorn",
                "--bind", f"{args.host}:{args.port}",
                "buem.apis.api_server:create_app()",
                "--workers", str(args.workers),
                "--threads", "2",
            ]
            print(
                f"Starting Gunicorn on http://{args.host}:{args.port}"
                f" ({args.workers} workers)"
            )
            sys.exit(subprocess.run(cmd).returncode)

    # ── validate ─────────────────────────────────────────────────────────────
    elif args.command == "validate":
        _run_validate()

    # ── multibuilding ─────────────────────────────────────────────────────────
    elif args.command == "multibuilding":
        import sys as _sys
        # Forward --buildings and --workers as sys.argv so run_multibuilding_demo
        # argparse picks them up.
        _argv = []
        if args.buildings:
            _argv += ["--buildings", str(args.buildings)]
        if args.workers:
            _argv += ["--workers", str(args.workers)]
        if args.sequential:
            _argv += ["--mode", "sequential"]
        _sys.argv = [_sys.argv[0]] + _argv

        from buem.parallelization.run_multibuilding_demo import main as mb_main

        mb_main()


def _run_validate() -> None:
    """Quick environment health-check printed to stdout."""
    import os
    from pathlib import Path

    ok = True
    lines: list[str] = []

    # Package imports
    for pkg in ("pandas", "numpy", "pvlib", "cvxpy"):
        try:
            __import__(pkg)
            lines.append(f"  [OK]  {pkg}")
        except ImportError as exc:
            lines.append(f"  [ERR] {pkg}: {exc}")
            ok = False

    try:
        from buem.thermal.model_buem import ModelBUEM  # noqa: F401

        lines.append("  [OK]  buem.thermal.model_buem.ModelBUEM")
    except ImportError as exc:
        lines.append(f"  [ERR] ModelBUEM: {exc}")
        ok = False

    # Environment variables
    for var, default_note in [
        ("BUEM_WEATHER_DIR", "auto: <package>/data"),
        ("BUEM_RESULTS_DIR", "auto: <package>/results"),
        ("BUEM_LOG_DIR",     "auto: <package>/logs"),
    ]:
        val = os.environ.get(var)
        if val:
            exists = "exists" if Path(val).exists() else "MISSING"
            lines.append(f"  [ENV] {var} = {val}  [{exists}]")
            if exists == "MISSING":
                ok = False
        else:
            lines.append(f"  [ENV] {var} = (not set; default: {default_note})")

    print("BUEM Environment Validation")
    print("=" * 40)
    for line in lines:
        print(line)
    print("=" * 40)
    print("PASS" if ok else "FAIL — see errors above")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
