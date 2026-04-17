import asyncio
import logging

from aiohttp import web

logger = logging.getLogger(__name__)


class OAuthTimeoutError(Exception):
    pass


class OAuthCallbackServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._pending: dict[str, asyncio.Future] = {}
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/callback/google", self._handle)
        app.router.add_get("/callback/microsoft", self._handle)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info("OAuth callback server listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            logger.info("OAuth callback server stopped")

    def register_state(self, state: str) -> asyncio.Future:
        """Register a state token and return a Future that resolves to the auth code."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[state] = future
        return future

    def cancel_state(self, state: str) -> None:
        future = self._pending.pop(state, None)
        if future and not future.done():
            future.cancel()

    async def _handle(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")

        future = self._pending.pop(state, None) if state else None

        if error or not code or future is None:
            if future and not future.done():
                future.set_exception(OAuthTimeoutError(f"OAuth error: {error or 'unknown'}"))
            return web.Response(
                text="<html><body><h2>Authentication failed. Please try again.</h2></body></html>",
                content_type="text/html",
                status=400,
            )

        if not future.done():
            future.set_result(code)

        return web.Response(
            text="<html><body><h2>Authentication successful! You can close this tab.</h2></body></html>",
            content_type="text/html",
        )
