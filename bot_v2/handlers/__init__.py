from aiogram import Router

from bot_v2.handlers import start, diagnostics, program, payments, jarwas, curator, miniapp

def setup_routers() -> Router:
    root = Router()
    root.include_router(start.router)
    root.include_router(diagnostics.router)
    root.include_router(program.router)
    root.include_router(payments.router)
    root.include_router(jarwas.router)
    root.include_router(curator.router)
    root.include_router(miniapp.router)
    return root
