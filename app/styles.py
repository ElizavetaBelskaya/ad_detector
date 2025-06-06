
MAIN_STYLE = """
    QWidget {
        background-color: #2E3440;
        color: #D8DEE9;
        font-size: 16px;
    }
    QLabel {
        color: #D8DEE9;
    }
    QPushButton {
        background-color: #5E81AC;
        color: #ECEFF4;
        padding: 5px;
        font-size: 16px;
        border-radius: 5px;
    }
    QPushButton:hover {
        background-color: #81A1C1;
    }
    QPushButton:disabled {
        background-color: #4C566A;
        color: #81A1C1;
    }
    QLineEdit {
        background-color: #3B4252;
        color: #D8DEE9;
        border: 1px solid #4C566A;
        border-radius: 4px;
        padding: 5px;
    }
    QLineEdit:focus {
        border: 1px solid #81A1C1;
    }
    QGroupBox {
        border: 1px solid #4C566A;
        border-radius: 5px;
        margin-top: 1em;
        padding-top: 10px;
    }
    QGroupBox::title {
        color: #81A1C1;
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px;
    }
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    QScrollBar:vertical {
        border: none;
        background: #3B4252;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #4C566A;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
"""

VIDEO_LABEL_STYLE = """
    border: 1px dashed #D8DEE9;
    padding: 5px;
    font-size: 14px;
    margin: 2px;
    min-height: 30px;
    max-height: 30px;
"""

VIDEO_INFO_LABEL_STYLE = """
    padding: 10px;
    font-size: 16px;
    margin: 0px;
    background-color: transparent;
"""

TIME_LABEL_STYLE = """
    color: #E2E8F0;
    font-size: 14px;
"""

AD_SLIDER_STYLE = """
    QWidget {
        background-color: #2D3748;
        border-radius: 4px;
    }
"""

BUTTON_STYLES = {
    'normal': """
        background-color: #5E81AC;
        color: #ECEFF4;
    """,
    'hover': """
        background-color: #81A1C1;
    """,
    'disabled': """
        background-color: #4C566A;
        color: #81A1C1;
    """
}

HTML_STYLES = {
    'container': """
        background-color: #2E3440;
        padding: 20px;
        border-radius: 10px;
    """,
    'header': """
        color: #88C0D0;
        margin-bottom: 20px;
        text-align: center;
    """,
    'segment': """
        background-color: #3B4252;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    """,
    'text': """
        color: #E5E9F0;
        margin: 0;
    """
}


def get_html_style(style_name: str) -> str:
    return HTML_STYLES.get(style_name, '')


def get_button_style(state: str = 'normal') -> str:
    return BUTTON_STYLES.get(state, BUTTON_STYLES['normal'])
