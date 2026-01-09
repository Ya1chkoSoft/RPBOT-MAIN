---
description: Правила по структуре кода
---

Strictly adhere to the Telegram bot project architecture: Session management and transactions ONLY in SessionMiddleware, NO manual session.commit() or session.rollback() in handlers, all Database interactions ONLY through functions in requests.py, handlers mutate DB objects but NO try/except wrapping DB operations (except input validation), session injected automatically.