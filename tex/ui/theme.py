from __future__ import annotations

BG = "#101318"
SURFACE = "#171B22"
CARD = "#1D232C"
BORDER = "#2A313D"
TEXT = "#E6EAF0"
MUTED = "#8B93A1"
ACCENT = "#F5A623"
ACCENT_HOVER = "#FFB84D"
ACCENT_DARK = "#1A1207"
OK = "#7EE787"
ERR = "#FF6B6B"

MONO_FAMILY = '"JetBrains Mono", "DejaVu Sans Mono", "Liberation Mono", monospace'

QSS = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10pt;
}}
QMainWindow, QDialog {{ background-color: {BG}; }}
QLabel {{ background: transparent; }}
QLabel#logo {{ font-size: 16pt; font-weight: 700; color: {ACCENT}; }}
QLabel#muted, QLabel#hint {{ color: {MUTED}; }}
QLabel#hint {{ font-size: 9pt; }}
QLabel#imagePreview {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#emptyIcon {{ font-size: 48pt; color: {MUTED}; }}
QLabel#emptyTitle {{ font-size: 14pt; font-weight: 600; color: {TEXT}; }}
QLabel#emptySub {{ font-size: 10pt; color: {MUTED}; }}

QPushButton {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: #232A35; }}
QPushButton:disabled {{ color: #566072; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{
    background-color: {ACCENT}; color: {ACCENT_DARK}; font-weight: 600; border: none;
}}
QPushButton[variant="primary"]:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton[variant="primary"]:pressed {{ background-color: #D48E1A; }}
QPushButton[variant="primary"]:disabled {{ background-color: #2A3B49; color: #7C93A3; }}

QToolButton {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 10px;
}}
QToolButton:hover {{ border-color: {ACCENT}; }}
QToolButton:pressed {{ background-color: #232A35; }}
QToolButton#modeCard {{ min-width: 128px; min-height: 92px; font-weight: 600; }}
QToolButton#iconBtn {{ border: none; background: transparent; border-radius: 6px; padding: 6px; }}
QToolButton#iconBtn:hover {{ background: {CARD}; }}

QComboBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 5px 10px; min-width: 120px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {MUTED}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER};
    selection-background-color: #24455C; selection-color: {TEXT};
}}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 5px 8px; selection-background-color: #24455C;
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}

QCheckBox {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid {BORDER};
    border-radius: 4px; background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QListWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 4px;
}}
QListWidget::item {{ border-radius: 6px; padding: 6px; margin: 2px; }}
QListWidget::item:hover {{ background: #1D2634; }}
QListWidget::item:selected {{ background: #223041; color: {TEXT}; }}

QStatusBar {{ background: #12161C; border-top: 1px solid {BORDER}; color: {MUTED}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #3A4350; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: #3A4350; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 8px; }}
QDialogButtonBox QPushButton {{ min-width: 84px; }}

QFrame#toast {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    border-left: 3px solid {MUTED};
}}
QFrame#toastSuccess {{
    background: #16281C; border: 1px solid {OK}; border-radius: 8px;
    border-left: 3px solid {OK};
}}
QFrame#toastError {{
    background: #2A1719; border: 1px solid {ERR}; border-radius: 8px;
    border-left: 3px solid {ERR};
}}
QLabel#toastText {{ background: transparent; }}
QPushButton#toastClose {{
    background: transparent; border: none; color: {MUTED}; font-size: 12pt;
    padding: 2px 6px; border-radius: 4px;
}}
QPushButton#toastClose:hover {{ color: {TEXT}; background: {CARD}; }}

QFrame#settingsSection {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 12px;
}}
QLabel#settingsSectionTitle {{ font-size: 10pt; font-weight: 600; color: {ACCENT};
    text-transform: uppercase; letter-spacing: 0.5px; background: transparent; }}

QPushButton#pill {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 13px;
    padding: 3px 12px; font-weight: 600; font-family: {MONO_FAMILY};
}}
QPushButton#pill:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#pill:pressed {{ background: {CARD}; }}
"""
