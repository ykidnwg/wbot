"""Safe platform adapter boundary for browser automation."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.models.browser import BrowserAccount

BrowserOutcomeStatus = Literal["SUCCESS", "FAILED", "NEEDS_USER_ACTION", "UNKNOWN"]


@dataclass(frozen=True)
class BrowserOutcome:
    status: BrowserOutcomeStatus
    message: str
    external_post_id: str | None = None
    published_url: str | None = None
    error_category: str | None = None
    retryable: bool = False


class BrowserPageSession(Protocol):
    page: Any

    async def storage_state(self) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class BrowserAdapter(Protocol):
    platform: str

    async def publish(
        self,
        session: BrowserPageSession,
        *,
        account: BrowserAccount,
        caption: str,
        media_path: str | None,
        target_url: str | None,
    ) -> BrowserOutcome: ...

    async def check_session(
        self,
        session: BrowserPageSession,
        *,
        account: BrowserAccount,
        target_url: str | None,
    ) -> BrowserOutcome: ...

    async def login(
        self,
        session: BrowserPageSession,
        *,
        account: BrowserAccount,
        timeout_seconds: float,
    ) -> BrowserOutcome: ...


@dataclass(frozen=True)
class FacebookBrowserConfig:
    base_url: str = "https://www.facebook.com"
    publish_enabled: bool = False
    authenticated_selector: str = '[aria-label="Your profile"]'
    challenge_selector: str = "text=security check"
    composer_url: str | None = None
    caption_selector: str = '[contenteditable="true"][role="textbox"]'
    submit_selector: str = '[aria-label="Post"]'
    success_selector: str | None = None
    media_input_selector: str = 'input[type="file"]'


class FacebookBrowserAdapter:
    """Conservative Facebook web adapter.

    Publishing is disabled unless explicitly enabled. Even when enabled this
    adapter only interacts with the visible composer; it never bypasses a
    challenge, CAPTCHA, or MFA step.
    """

    platform = "facebook"

    def __init__(self, config: FacebookBrowserConfig) -> None:
        self.config = config

    async def login(
        self,
        session: BrowserPageSession,
        *,
        account: BrowserAccount,
        timeout_seconds: float,
    ) -> BrowserOutcome:
        del account
        page = session.page
        try:
            await page.goto(
                f"{self.config.base_url.rstrip('/')}/login",
                wait_until="domcontentloaded",
                timeout=timeout_seconds * 1000,
            )
            await page.locator(self.config.authenticated_selector).first.wait_for(
                state="visible", timeout=timeout_seconds * 1000
            )
        except Exception:
            return BrowserOutcome(
                status="NEEDS_USER_ACTION",
                message=(
                    "Manual login was not completed in the visible browser. "
                    "Sign in manually and run the login job again."
                ),
                error_category="auth",
            )
        return BrowserOutcome(status="SUCCESS", message="Browser session captured")

    async def check_session(
        self,
        session: BrowserPageSession,
        *,
        account: BrowserAccount,
        target_url: str | None,
    ) -> BrowserOutcome:
        del account
        page = session.page
        try:
            await page.goto(
                target_url or self.config.base_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if await _is_visible(page, self.config.challenge_selector):
                return BrowserOutcome(
                    status="NEEDS_USER_ACTION",
                    message="A platform security check requires manual attention.",
                    error_category="auth",
                )
            if "/login" in str(page.url).lower() or not await _is_visible(
                page, self.config.authenticated_selector
            ):
                return BrowserOutcome(
                    status="NEEDS_USER_ACTION",
                    message="The saved browser session is no longer signed in.",
                    error_category="auth",
                )
        except Exception:
            return BrowserOutcome(
                status="FAILED",
                message="The browser could not verify the saved session.",
                error_category="network",
                retryable=True,
            )
        return BrowserOutcome(status="SUCCESS", message="Session appears healthy")

    async def publish(
        self,
        session: BrowserPageSession,
        *,
        account: BrowserAccount,
        caption: str,
        media_path: str | None,
        target_url: str | None,
    ) -> BrowserOutcome:
        if not self.config.publish_enabled:
            return BrowserOutcome(
                status="NEEDS_USER_ACTION",
                message=(
                    "Facebook browser publishing is disabled until this deployment's "
                    "workflow has been reviewed and enabled."
                ),
                error_category="permission",
            )
        page = session.page
        try:
            await page.goto(
                self.config.composer_url or target_url or self.config.base_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if await _is_visible(page, self.config.challenge_selector):
                return BrowserOutcome(
                    status="NEEDS_USER_ACTION",
                    message="A platform security check stopped the workflow.",
                    error_category="auth",
                )
            if "/login" in str(page.url).lower():
                return BrowserOutcome(
                    status="NEEDS_USER_ACTION",
                    message="The saved browser session is no longer signed in.",
                    error_category="auth",
                )
            if media_path:
                await page.locator(self.config.media_input_selector).first.set_input_files(
                    media_path
                )
            await page.locator(self.config.caption_selector).first.fill(caption)
            await page.locator(self.config.submit_selector).first.click()
        except Exception:
            return BrowserOutcome(
                status="FAILED",
                message="The browser workflow failed before the post was submitted.",
                error_category="temporary",
                retryable=True,
            )
        try:
            if self.config.success_selector:
                await page.locator(self.config.success_selector).first.wait_for(
                    state="visible", timeout=30_000
                )
            else:
                await page.wait_for_timeout(2_000)
        except Exception:
            return BrowserOutcome(
                status="UNKNOWN",
                message=(
                    "The post may have been submitted, but no confirmation was visible. "
                    "Verify the account before retrying."
                ),
                error_category="uncertain",
            )
        return BrowserOutcome(
            status="SUCCESS",
            message="The visible browser confirmed the post.",
            published_url=str(page.url),
        )


async def _is_visible(page: Any, selector: str | None) -> bool:
    if not selector:
        return False
    try:
        return bool(
            await page.locator(selector).first.is_visible(timeout=2_000)
        )
    except Exception:
        return False
