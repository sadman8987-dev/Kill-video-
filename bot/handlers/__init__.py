from aiogram import Router

from . import admin, user


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(admin.router)  # admin first so /stats etc. never fall into the text handler
    root.include_router(user.router)
    return root
