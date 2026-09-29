"""Capture synthetic P0 review views; output directory is explicitly supplied."""
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from woff.p0_desktop.window import P0Window


def main(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    window = P0Window()
    window.show()
    app.processEvents()
    for filename, screen, state, career_index in (
        ('operations-ready.png', 'OPR-01', 'ready', 0),
        ('dossier-ready.png', 'DOS-01', 'ready', 0),
        ('missions-error.png', 'MIS-01', 'error', 0),
        ('homonym-missing.png', 'DOS-01', 'ready', 1),
    ):
        window.career.setCurrentIndex(career_index)
        window.navigate(screen)
        window.set_fixture_state(state)
        app.processEvents()
        if not window.grab().save(str(output / filename)):
            raise RuntimeError('P0 screenshot capture failed')
    window.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/capture_p0.py OUTPUT_DIRECTORY')
    main(Path(sys.argv[1]))
