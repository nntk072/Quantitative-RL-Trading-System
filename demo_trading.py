"""Compatibility entrypoint for the single-symbol MT5 demo."""

from integrations.mt5.cli import single_symbol_demo as _application

get_robot = _application.get_robot
run_job = _application.run_job
schedule_hourly = _application.schedule_hourly
start_scheduler = _application.start_scheduler


def main() -> None:
    """Run the demo application."""
    _application.main()


if __name__ == "__main__":
    main()
