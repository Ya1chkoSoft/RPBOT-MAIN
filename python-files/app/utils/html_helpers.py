import html

def escape_html(text: str) -> str:
    """Безопасное экранирование для HTML"""
    return html.escape(str(text), quote=False)

def hbold(text: str) -> str:
    """Безопасно делает текст жирным"""
    return f"<b>{escape_html(text)}</b>"

def hitalic(text: str) -> str:
    """Безопасно делает текст курсивом"""  
    return f"<i>{escape_html(text)}</i>"

def hcode(text: str) -> str:
    """Безопасно делает текст моноширинным"""
    return f"<code>{escape_html(text)}</code>"

def hlink(text: str, url: str) -> str:
    """Безопасно делает ссылку"""
    return f"<a href='{escape_html(url)}'>{escape_html(text)}</a>"