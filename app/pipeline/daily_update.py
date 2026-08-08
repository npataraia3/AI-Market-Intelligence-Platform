"""Free daily ETL entry point for GitHub Actions or a local scheduler."""

from app.data.database import initialize_database, save_snapshots
from app.services.market_data import fetch_market_data
from app.services.monitoring import create_alerts


def main() -> None:
    initialize_database()
    market_data = fetch_market_data()
    saved = save_snapshots(market_data)
    alerts = create_alerts(market_data)
    print(f"Daily pipeline completed: {saved} snapshots saved, {len(alerts)} alerts created.")


if __name__ == "__main__":
    main()
