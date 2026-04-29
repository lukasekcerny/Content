from app.constants import COLORS as C


def build_stylesheet() -> str:
    return f"""
    /* ===== Global ===== */
    QWidget {{
        background-color: {C.bg_app};
        color: {C.text_primary};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
        selection-background-color: {C.bg_card_active};
        selection-color: {C.text_primary};
    }}

    /* ===== Main Window ===== */
    QMainWindow {{
        background-color: {C.bg_app};
    }}

    /* ===== Scroll Areas ===== */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        background: {C.bg_shell};
        width: 8px;
        margin: 0;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {C.border_default};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {C.border_strong};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        height: 0;
        background: none;
        border: none;
    }}
    QScrollBar:horizontal {{
        background: {C.bg_shell};
        height: 8px;
        margin: 0;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {C.border_default};
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {C.border_strong};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        width: 0;
        background: none;
        border: none;
    }}

    /* ===== Labels ===== */
    QLabel {{
        background-color: transparent;
        border: none;
        color: {C.text_secondary};
    }}
    QLabel[role="title"] {{
        color: {C.text_primary};
        font-size: 16px;
        font-weight: 600;
    }}
    QLabel[role="heading"] {{
        color: {C.text_primary};
        font-size: 14px;
        font-weight: 600;
    }}
    QLabel[role="muted"] {{
        color: {C.text_muted};
        font-size: 12px;
    }}
    QLabel[role="disabled"] {{
        color: {C.text_disabled};
    }}

    /* ===== Frames (panels, cards) ===== */
    QFrame[role="panel"] {{
        background-color: {C.bg_panel};
        border: none;
    }}
    QFrame[role="card"] {{
        background-color: {C.bg_card};
        border: 1px solid {C.border_soft};
        border-radius: 12px;
    }}
    QFrame[role="card"]:hover {{
        background-color: {C.bg_card_hover};
    }}
    QFrame[role="card_active"] {{
        background-color: {C.bg_card_active};
        border: 1px solid {C.border_default};
        border-radius: 12px;
    }}
    QFrame[role="popup"] {{
        background-color: {C.bg_popup};
        border: 1px solid {C.border_default};
        border-radius: 12px;
    }}
    QFrame[role="header"] {{
        background-color: {C.bg_panel};
        border: none;
        border-bottom: 1px solid {C.border_soft};
    }}
    QFrame[role="sidebar"] {{
        background-color: {C.bg_panel};
        border: none;
        border-right: 1px solid {C.border_soft};
    }}

    /* ===== Buttons ===== */
    QPushButton {{
        background-color: {C.bg_card_hover};
        color: {C.text_primary};
        border: 1px solid {C.border_default};
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {C.bg_card_active};
        border-color: {C.border_strong};
    }}
    QPushButton:pressed {{
        background-color: {C.bg_card};
    }}
    QPushButton:disabled {{
        color: {C.text_disabled};
        background-color: {C.bg_card};
        border-color: {C.border_soft};
    }}

    QPushButton[role="primary"] {{
        background-color: {C.primary_bg};
        color: {C.primary_text};
        border: none;
        font-weight: 600;
    }}
    QPushButton[role="primary"]:hover {{
        background-color: {C.primary_hover};
    }}
    QPushButton[role="primary"]:pressed {{
        background-color: {C.primary_pressed};
    }}
    QPushButton[role="primary"]:disabled {{
        background-color: {C.border_default};
        color: {C.text_disabled};
    }}

    QPushButton[role="ghost"] {{
        background-color: transparent;
        color: {C.text_secondary};
        border: none;
    }}
    QPushButton[role="ghost"]:hover {{
        background-color: #1A1C1E;
    }}

    QPushButton[role="danger"] {{
        background-color: {C.danger_bg};
        color: {C.danger_text};
        border: 1px solid #5A2F2F;
    }}
    QPushButton[role="danger"]:hover {{
        background-color: {C.danger};
        color: {C.text_primary};
    }}

    /* ===== Inputs ===== */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {C.bg_input};
        color: {C.text_primary};
        border: 1px solid {C.border_soft};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {C.border_strong};
        background-color: #141516;
    }}
    QLineEdit:disabled, QTextEdit:disabled {{
        color: {C.text_disabled};
        background-color: {C.bg_shell};
    }}
    QLineEdit[echoMode="2"] {{
        lineedit-password-character: 9679;
    }}

    /* ===== Combo Box ===== */
    QComboBox {{
        background-color: {C.bg_input};
        color: {C.text_primary};
        border: 1px solid {C.border_soft};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
    }}
    QComboBox:hover {{
        border-color: {C.border_default};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {C.bg_popup};
        color: {C.text_primary};
        border: 1px solid {C.border_default};
        selection-background-color: {C.bg_card_active};
        outline: none;
    }}

    /* ===== Check Box ===== */
    QCheckBox {{
        color: {C.text_secondary};
        spacing: 8px;
        background-color: transparent;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {C.border_default};
        border-radius: 4px;
        background-color: {C.bg_input};
    }}
    QCheckBox::indicator:checked {{
        background-color: {C.success};
        border-color: {C.success};
    }}
    QCheckBox::indicator:hover {{
        border-color: {C.border_strong};
    }}
    QCheckBox:disabled {{
        color: {C.text_disabled};
    }}
    QCheckBox::indicator:disabled {{
        background-color: {C.bg_shell};
        border-color: {C.border_soft};
    }}

    /* ===== Tab Widget ===== */
    QTabWidget::pane {{
        border: none;
        background-color: {C.bg_app};
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {C.text_muted};
        padding: 10px 16px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 13px;
    }}
    QTabBar::tab:hover {{
        color: {C.text_secondary};
        background-color: {C.bg_card};
    }}
    QTabBar::tab:selected {{
        color: {C.text_primary};
        border-bottom-color: {C.border_strong};
        font-weight: 600;
    }}

    /* ===== Progress Bar ===== */
    QProgressBar {{
        background-color: {C.bg_input};
        border: none;
        border-radius: 2px;
        max-height: 4px;
        min-height: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        border-radius: 2px;
    }}
    QProgressBar[phase="import"]::chunk {{
        background-color: {C.border_strong};
    }}
    QProgressBar[phase="upload"]::chunk {{
        background-color: {C.warning};
    }}
    QProgressBar[phase="done"]::chunk {{
        background-color: {C.success};
    }}
    QProgressBar[phase="error"]::chunk {{
        background-color: {C.danger};
    }}
    QProgressBar[size="large"] {{
        max-height: 6px;
        min-height: 6px;
    }}

    /* ===== Tool Tip ===== */
    QToolTip {{
        background-color: {C.bg_popup};
        color: {C.text_primary};
        border: 1px solid {C.border_default};
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 12px;
    }}

    /* ===== Menu ===== */
    QMenu {{
        background-color: {C.bg_popup};
        color: {C.text_primary};
        border: 1px solid {C.border_default};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {C.bg_card_active};
    }}

    /* ===== Splitter ===== */
    QSplitter::handle {{
        background-color: {C.border_soft};
        width: 1px;
    }}

    /* ===== Dialog ===== */
    QDialog {{
        background-color: {C.bg_popup};
    }}
    """
