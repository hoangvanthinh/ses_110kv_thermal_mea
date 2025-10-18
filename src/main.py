"""Main entry point for thermal camera monitoring system."""
from nicegui import ui, app

from worker_manager import WorkerManager
from utils.logging import get_logger
from ui_app import register_pages

log = get_logger("main")


def main() -> None:
    """Main application entry point."""
    # Initialize worker manager
    worker_manager = WorkerManager()
    
    # Start all workers
    threads, out_queue = worker_manager.start_all()

    # UI setup (commented out until ready)
    # register_pages(out_queue)

    # Register shutdown hook
    @app.on_shutdown
    def _cleanup() -> None:
        """Clean up workers on application shutdown."""
        worker_manager.stop_all()

    # Run the NiceGUI application
    ui.run(
        port=8080,
        reload=False,
        storage_secret='super-secret-key',
        title='Thermal Camera Monitor'
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
