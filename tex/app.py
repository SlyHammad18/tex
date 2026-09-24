from __future__ import annotations

import json
import sys

from PySide6.QtCore import QLoggingCategory, QtMsgType, qInstallMessageHandler
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from tex import __version__
from tex import config as cfgmod
from tex.cli import parse_args
from tex.ui import theme
from tex.ui.icons import app_icon
from tex.ui.main_window import MainWindow

INSTANCE_NAME = "tex-app-instance"

_QUIET_MESSAGES = (
    "Failed to register with host portal",
    "Paint device returned engine == 0",
    "Painter not active",
)


def _qt_message_handler(mode, context, message) -> None:
    for quiet in _QUIET_MESSAGES:
        if quiet in message:
            return
    print(message, file=sys.stderr)


def _install_quiet_logging() -> None:
    QLoggingCategory.setFilterRules("qt.qpa.services.warning=false")
    qInstallMessageHandler(_qt_message_handler)


def _forward_to_instance(args) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(json.dumps(vars(args)).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _install_quiet_logging()

    app = QApplication(["tex"])
    app.setApplicationName("Tex")
    app.setOrganizationName("Tex")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())

    if _forward_to_instance(args):
        return 0

    app.setStyleSheet(theme.QSS)

    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_NAME)
    if not server.listen(INSTANCE_NAME):
        server = None  # type: ignore[assignment]

    win = MainWindow(cfgmod.load_config(), args)
    win.show()

    if server is not None:
        def _on_connection():
            conn = server.nextPendingConnection()
            if conn is None:
                return
            if conn.waitForReadyRead(500):
                try:
                    payload = json.loads(bytes(conn.readAll()).decode("utf-8"))
                except Exception:
                    payload = None
                if payload:
                    win.handle_remote(payload)
            conn.disconnectFromServer()

        server.newConnection.connect(_on_connection)
        app.aboutToQuit.connect(server.close)

    return app.exec()
