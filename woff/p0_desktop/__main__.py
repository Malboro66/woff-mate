"""Run the experimental fixture-backed P0 desktop."""
import sys
from PySide6.QtWidgets import QApplication
from .window import P0Window


def main() -> int:
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != "--smoke"):
        raise SystemExit("Usage: python -m woff.p0_desktop [--smoke]")
    app = QApplication(sys.argv)
    window = P0Window()
    window.show()
    if len(sys.argv) == 2:
        app.processEvents()
        window.close()
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
