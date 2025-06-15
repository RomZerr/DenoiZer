"""
Styles.py - Module contenant les styles utilisés dans l'application DenoiZer
"""

MAIN_STYLE = """
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
        font-size: 12px;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QLineEdit, QTextEdit, QComboBox {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 5px;
    }
    QListWidget {
        background-color: transparent;
        color: #e0e0e0;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 5px;
        alternate-background-color: transparent;
    }
    QPushButton {
        background-color: #0078d7;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px;
        min-height: 20px;
        font-weight: bold;
    }
    QPushButton#actionButton {
        min-height: 40px;
    }
    QPushButton:hover {
        background-color: #0086f0;
    }
    QPushButton:pressed {
        background-color: #005fa3;
    }
    QPushButton:disabled {
        background-color: #444444;
        color: #999999;
    }
    QCheckBox {
        spacing: 5px;
    }
    QProgressBar {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: none;
        border-radius: 4px;
        text-align: center;
        height: 12px;
    }
    QProgressBar::chunk {
        background-color: #0078d7;
        border-radius: 4px;
    }
    QGroupBox {
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        margin-top: 1.5em;
        padding-top: 1em;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
        color: #0078d7;
    }
    QLabel {
        padding: 2px;
    }
    QSplitter::handle {
        background-color: #3c3c3c;
    }
    QScrollBar:vertical {
        border: none;
        background: #2d2d2d;
        width: 12px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #555555;
        min-height: 20px;
        border-radius: 3px;
    }
    QComboBox {
        padding: 5px;
        border-radius: 4px;
        min-width: 6em;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 1px;
        border-left-color: #3c3c3c;
        border-left-style: solid;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
    }
    QComboBox::down-arrow {
        border-width: 5px;
        border-style: solid;
        border-color: #e0e0e0 transparent transparent transparent;
        width: 0px;
        height: 0px;
    }
    #collapsibleSection {
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        margin: 5px 0px;
    }
    #signature {
        color: #666666;
        font-style: italic;
    }
"""

LOG_WINDOW_STYLE = """
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QTextEdit {
        background-color: #2d2d2d;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 5px;
    }
    QProgressBar {
        text-align: center;
        height: 20px;
        background-color: #2d2d2d;
        border: none;
        border-radius: 4px;
    }
    QProgressBar::chunk {
        background-color: #0078d7;
        border-radius: 4px;
    }
"""

SIGNATURE_STYLE = """
    QLabel#signature {
        color: #666666;
        font-style: italic;
        padding: 5px;
        font-size: 11px;
    }
"""

STATUS_LABEL_STYLE = "font-size: 14px; font-weight: bold; color: #0078d7;"
TIME_LABEL_STYLE = "font-size: 12px; color: #e0e0e0;"

TOGGLE_BUTTON_STYLE = """
    QToolButton {
        border: none;
        background-color: transparent;
    }
"""

SECTION_TITLE_STYLE = """
    QLabel {
        color: #0078d7;
        font-size: 14px;
    }
"""

# Couleurs utilisées dans l'application
COLORS = {
    "background": "#1e1e1e",
    "secondary_background": "#2d2d2d",
    "border": "#3c3c3c",
    "text": "#e0e0e0",
    "primary": "#0078d7",
    "primary_hover": "#0086f0",
    "primary_pressed": "#005fa3",
    "disabled": "#444444",
    "disabled_text": "#999999",
    "alternate_row": "#252525",
    "scrollbar": "#555555",
    "signature": "#666666"
} 