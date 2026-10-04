import sys
import os
import faulthandler
import argparse
import logging
from pathlib import Path

faulthandler.enable()

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit

from configparser import ConfigParser
from src.model import ForensicModel, BASE_DIR
from src.view import ForensicView
from src.presenter import ForensicPresenter
from src.utils.logging_config import setup_logging, set_log_context

PROJECT_INI = BASE_DIR / "config" / "project.ini"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Video Forensic Analyzer")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable console INFO logging")
    parser.add_argument("--debug", action="store_true", help="Enable console DEBUG logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    console_level = logging.WARNING
    if args.debug:
        console_level = logging.DEBUG
    elif args.verbose:
        console_level = logging.INFO

    setup_logging(console_level=console_level)

    app = QApplication(sys.argv)

    def excepthook(typ, val, tb):
        import traceback
        msg = "".join(traceback.format_exception(typ, val, tb))
        logging.critical("UNHANDLED EXCEPTION:\n%s", msg)
    sys.excepthook = excepthook

    model = ForensicModel()

    if not model.db_config.get('password'):
        root_pw, ok_root = QInputDialog.getText(
            None, "Initiales Setup",
            "MariaDB 'root' Passwort eingeben:",
            echo=QLineEdit.EchoMode.Password
        )

        if ok_root and root_pw:
            user_pw, ok_user = QInputDialog.getText(
                None, "Initiales Setup",
                "Neues Passwort für den Analyzer-User (va_user) festlegen:",
                echo=QLineEdit.EchoMode.Password
            )

            if ok_user and user_pw:
                try:
                    model.initial_root_setup(root_pw, user_pw)
                    QMessageBox.information(
                        None, "Setup Erfolg",
                        "Datenbank wurde erfolgreich konfiguriert und mariadb.ini erstellt."
                    )
                except Exception as e:
                    QMessageBox.critical(
                        None, "Setup Fehler",
                        f"Fehler beim Erstellen der Datenbank:\n{e}"
                    )
                    return
            else:
                return
        else:
            return

    if not PROJECT_INI.exists():
        from PyQt6.QtWidgets import QFileDialog
        from configparser import ConfigParser

        QMessageBox.information(
            None,
            "Projekt-Speicherort",
            "Bitte wählen Sie den Standard-Speicherort für alle Fälle aus."
        )

        folder = QFileDialog.getExistingDirectory(
            None,
            "Speicherort für Fälle auswählen"
        )

        if not folder:
            QMessageBox.critical(
                None,
                "Abbruch",
                "Es wurde kein Speicherort gewählt. Programm wird beendet."
            )
            return

        parser = ConfigParser()
        parser.add_section("settings")
        parser.set("settings", "case_root", str(Path(folder).resolve()))

        PROJECT_INI.parent.mkdir(parents=True, exist_ok=True)
        with open(PROJECT_INI, "w") as f:
            parser.write(f)

        model.load_project_config()

        QMessageBox.information(
            None,
            "Gespeichert",
            f"Standard-Speicherort wurde gesetzt:\n{folder}"
        )

    if model.current_case_path:
        setup_logging(case_path=model.current_case_path, console_level=console_level)
        set_log_context(case_id=model.current_case_id)

    try:
        view = ForensicView()
        presenter = ForensicPresenter(model, view)

        view.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical("Start Fehler: %s", e, exc_info=True)
        QMessageBox.critical(
            None, "Start Fehler",
            f"Anwendung konnte nicht gestartet werden:\n{e}"
        )


if __name__ == "__main__":
    main()