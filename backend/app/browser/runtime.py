"""Playwright runtime behind a small interface so tests never launch a browser."""

from typing import Any, Protocol

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from app.browser.adapters import BrowserPageSession


class BrowserRuntime(Protocol):
    async def start(self) -> None: ...

    async def new_session(
        self, *, storage_state: dict[str, Any] | None = None
    ) -> BrowserPageSession: ...

    async def close(self) -> None: ...


class PlaywrightBrowserSession:
    def __init__(self, context: BrowserContext) -> None:
        self.context = context
        self.page = None

    async def open(self) -> "PlaywrightBrowserSession":
        self.page = await self.context.new_page()
        return self

    async def storage_state(self) -> dict[str, Any]:
        return await self.context.storage_state()

    async def close(self) -> None:
        await self.context.close()


class PlaywrightBrowserRuntime:
    def __init__(
        self,
        *,
        headless: bool = True,
        no_sandbox: bool = False,
        timeout_ms: int = 30_000,
    ) -> None:
        self.headless = headless
        self.no_sandbox = no_sandbox
        self.timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        args = ["--no-sandbox"] if self.no_sandbox else []
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless, args=args
        )

    async def new_session(
        self, *, storage_state: dict[str, Any] | None = None
    ) -> BrowserPageSession:
        if self._browser is None:
            raise RuntimeError("Browser runtime has not been started")
        context = await self._browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1440, "height": 1000},
            locale="en-US",
        )
        context.set_default_timeout(self.timeout_ms)
        return await PlaywrightBrowserSession(context).open()

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
