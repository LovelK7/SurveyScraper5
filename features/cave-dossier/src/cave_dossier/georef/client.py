"""Playwright client for georef.hr — ported near-verbatim from
crospeleo-automation ``georef/client.py`` (see docs/PORTING.md).
Changed: imports + Settings source; the Settings field names are kept
identical so the flow logic reads the same on both sides."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from cave_dossier.core.config import Settings
from cave_dossier.georef.models import GeorefArtifacts, GeorefLoginResult, GeorefSession, GeorefStatus
from cave_dossier.georef.selectors import SelectorRegistry


LOGGER = logging.getLogger(__name__)

# Set GEOREF_TRACE_TIMING=1 in the environment to print wall-clock
# elapsed time before each login step.  Useful for diagnosing UI
# slowness at the granularity Playwright traces don't quite show.
_TRACE_TIMING = os.environ.get("GEOREF_TRACE_TIMING") == "1"


def _trace(label: str, t0: float) -> None:
    if _TRACE_TIMING:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        print(f"  [georef +{elapsed_ms:>5} ms]  {label}", flush=True)


# Short timeout for probing a YAML-configured primary selector inside
# the *_or_fallback helpers.  When the primary is stale (Georef DOM has
# changed since the selector was recorded), the helper falls through to
# the role/name fallback — which we want to happen quickly, not after
# the full 10 s default timeout.  Calibrated so a slow-but-valid primary
# still wins, while a stale primary doesn't burn 9 seconds per call site.
_PRIMARY_PROBE_TIMEOUT_MS = 1000
_FALLBACK_TIMEOUT_MS = 10000


class GeorefClient:
    def __init__(self, settings: Settings, selectors: dict[str, str], *, debug: bool = False) -> None:
        self.settings = settings
        self.selectors = SelectorRegistry(selectors)
        self.debug = debug

    def login(self, artifacts: GeorefArtifacts) -> tuple[GeorefLoginResult, GeorefSession | None]:
        if not self.settings.georef_base_url or not self.settings.georef_username or not self.settings.georef_password:
            return (
                GeorefLoginResult(
                    success=False,
                    georef_status=GeorefStatus.ERROR,
                    error_message="Missing Georef credentials or base URL in configuration (.env: GEOREF_BASE_URL / GEOREF_USERNAME / GEOREF_PASSWORD).",
                ),
                None,
            )

        t0 = time.monotonic()
        _trace("starting playwright + browser", t0)
        playwright = sync_playwright().start()
        browser_launcher = getattr(playwright, self.settings.playwright_browser)
        # Pin the headed window to a consistent size so the
        # marker-centered map crop math (in georef/flows.py) has
        # deterministic room around the pin.  Without this, Chromium
        # picks a default size that varies by display/DPI and the crop
        # constraints end up clamped asymmetrically.
        browser = browser_launcher.launch(
            headless=not self.debug,
            slow_mo=self.settings.playwright_slow_mo_ms,
            args=["--window-size=1440,900", "--window-position=0,0"],
        )
        # `no_viewport=True` disables Playwright's fixed-viewport emulation
        # so the page renders at the actual headed window size.  Without
        # this, Playwright snaps the page to its default 1280×720 viewport
        # whenever it re-asserts device emulation (focus changes, certain
        # waits), producing a visible zoom-out/zoom-in flicker against the
        # larger OS window.  `device_scale_factor` cannot be combined with
        # `no_viewport=True` (Playwright raises at new_context), so we drop
        # it — debug screenshots are viewport-only (full_page=False), and
        # the browser falls back to the OS's native DPR.
        context = browser.new_context(no_viewport=True)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        session = GeorefSession(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
            trace_path=artifacts.trace_path,
            browser_log_path=artifacts.browser_log_path,
        )
        _attach_page_logging(page, artifacts.browser_log_path)

        try:
            _trace("page.goto …", t0)
            page.goto(
                self.settings.georef_base_url,
                wait_until="domcontentloaded",
                timeout=self.settings.georef_navigation_timeout_ms,
            )
            _trace("after goto (DOM loaded)", t0)
            page.context.grant_permissions(["clipboard-read", "clipboard-write"])
            if self.debug:
                page.screenshot(path=str(artifacts.debug_dir / "login_start.png"), full_page=False)
                _trace("after screenshot login_start.png", t0)

            # Optional legacy splash: if the Georef login page renders a
            # "Start »" button before revealing the form, click it.  Use an
            # instant `is_visible()` probe rather than `wait_for(timeout=…)`
            # — the current login skips this splash and lands directly on
            # the username/password form, so a blocking wait would be pure
            # overhead before each run.  The branch still fires if the
            # splash ever reappears.
            landing_selector = self.selectors.optional("georef_landing_start_button")
            if landing_selector:
                landing = page.locator(landing_selector).first
                if landing.is_visible():
                    self.click(page, landing_selector)
            _trace("after landing-button probe", t0)

            # Login form primaries default to "" in selectors.yaml so the
            # _or_fallback helpers go straight to the role-based path
            # (which is what the live Georef DOM matches).  Use
            # `optional() or ""` so an empty/missing primary is allowed
            # to fall through; `require()` would raise instead.
            self.fill_or_fallback(
                page,
                self.selectors.optional("georef_login_username") or "",
                self.settings.georef_username,
                role="textbox",
                name="Korisničko ime",
            )
            _trace("after username fill", t0)
            self.fill_or_fallback(
                page,
                self.selectors.optional("georef_login_password") or "",
                self.settings.georef_password,
                role="textbox",
                name="Lozinka",
            )
            _trace("after password fill", t0)

            accept_terms = self.selectors.optional("georef_accept_terms")
            if accept_terms:
                self.check_or_fallback(page, accept_terms, name="Prihvaćam uvjete korištenja", optional=True)
            _trace("after accept-terms tick", t0)

            self.click_or_fallback(
                page,
                self.selectors.optional("georef_login_submit") or "",
                role="button",
                name="Prijava",
            )
            _trace("after Prijava click", t0)

            post_login = self.selectors.optional("georef_post_login_ready")
            if post_login:
                page.locator(post_login).first.wait_for(state="visible", timeout=15000)
            else:
                page.wait_for_load_state("networkidle", timeout=15000)
            _trace("after post-login wait (logged in)", t0)

            success_path = artifacts.debug_dir / "login_success.png"
            if self.debug:
                page.screenshot(path=str(success_path), full_page=False)
            return (
                GeorefLoginResult(
                    success=True,
                    georef_status=GeorefStatus.READY,
                    screenshot_path=str(success_path) if self.debug else None,
                    browser_log_path=str(artifacts.browser_log_path),
                ),
                session,
            )
        except Exception as exc:
            # Always capture the error screenshot — login failures need
            # the visual postmortem regardless of debug mode.
            error_path = artifacts.debug_dir / "login_error.png"
            try:
                page.screenshot(path=str(error_path), full_page=False, timeout=10_000)
            except Exception:
                error_path = None
            trace_path = self.close_session(session)
            return (
                GeorefLoginResult(
                    success=False,
                    georef_status=GeorefStatus.ERROR,
                    error_message=str(exc),
                    screenshot_path=str(error_path) if error_path else None,
                    trace_path=trace_path,
                    browser_log_path=str(artifacts.browser_log_path),
                ),
                None,
            )

    def close_session(self, session: GeorefSession) -> str:
        session.context.tracing.stop(path=str(session.trace_path))
        session.context.close()
        session.browser.close()
        try:
            session.playwright.stop()
        except Exception:
            LOGGER.debug("Playwright cleanup failed", exc_info=True)
        return str(session.trace_path)

    @staticmethod
    def locator(page: object, selector: str):
        return page.locator(selector).first

    def fill(self, page: object, selector: str, value: str) -> None:
        locator = self.locator(page, selector)
        locator.wait_for(state="visible", timeout=10000)
        locator.fill("")
        locator.fill(value)

    def fill_or_fallback(self, page: object, selector: str, value: str, *, role: str, name: str) -> None:
        # Empty primary → skip probe entirely and go straight to the
        # role-based fallback.  Otherwise probe with a short timeout
        # and fall through fast on miss.  See `_PRIMARY_PROBE_TIMEOUT_MS`
        # rationale at module scope.
        if selector:
            try:
                locator = self.locator(page, selector)
                locator.wait_for(state="visible", timeout=_PRIMARY_PROBE_TIMEOUT_MS)
                locator.fill("")
                locator.fill(value)
                return
            except PlaywrightTimeoutError:
                pass
        fallback = page.get_by_role(role, name=name).first
        fallback.wait_for(state="visible", timeout=_FALLBACK_TIMEOUT_MS)
        fallback.fill("")
        fallback.fill(value)

    def fill_with_fallback(self, page: object, selector: str, candidates: list[str]) -> str:
        if not candidates:
            raise ValueError(f"No coordinate candidates provided for selector: {selector}")

        locator = self.locator(page, selector)
        locator.wait_for(state="visible", timeout=10000)
        last_value = ""
        for candidate in candidates:
            locator.fill("")
            locator.fill(candidate)
            current_value = (locator.input_value() or "").strip()
            last_value = current_value
            if _equivalent_number_text(current_value, candidate):
                return candidate
        if last_value:
            LOGGER.warning("Coordinate input readback differed from candidates", extra={"selector": selector, "value": last_value})
        return candidates[-1]

    def click(self, page: object, selector: str, optional: bool = False) -> None:
        # `optional=True` callers explicitly accept "give up if not
        # present" semantics — make the give-up fast.  Required clicks
        # keep the full 10 s window because we genuinely need to wait
        # for the element to appear.
        timeout = _PRIMARY_PROBE_TIMEOUT_MS if optional else _FALLBACK_TIMEOUT_MS
        locator = self.locator(page, selector)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
        except PlaywrightTimeoutError:
            if not optional:
                raise

    def click_or_fallback(self, page: object, selector: str, *, role: str, name: str, optional: bool = False) -> None:
        # Empty primary → skip probe and use the role fallback.
        if selector:
            try:
                locator = self.locator(page, selector)
                locator.wait_for(state="visible", timeout=_PRIMARY_PROBE_TIMEOUT_MS)
                locator.click()
                return
            except PlaywrightTimeoutError:
                pass
        if optional:
            try:
                fallback = page.get_by_role(role, name=name).first
                fallback.wait_for(state="visible", timeout=_PRIMARY_PROBE_TIMEOUT_MS)
                fallback.click()
            except PlaywrightTimeoutError:
                return
            return
        fallback = page.get_by_role(role, name=name).first
        fallback.wait_for(state="visible", timeout=_FALLBACK_TIMEOUT_MS)
        fallback.click()

    def check_or_fallback(self, page: object, selector: str, *, name: str, optional: bool = False) -> None:
        # Probe primary with short timeout, fall through fast on miss.
        try:
            locator = self.locator(page, selector)
            locator.wait_for(state="visible", timeout=_PRIMARY_PROBE_TIMEOUT_MS)
            locator.check()
            return
        except PlaywrightTimeoutError:
            try:
                checkbox = page.get_by_role("checkbox", name=name).first
                checkbox.wait_for(state="visible", timeout=_FALLBACK_TIMEOUT_MS)
                checkbox.check()
            except PlaywrightTimeoutError:
                if not optional:
                    raise

    def text_content(self, page: object, selector: str) -> str | None:
        locator = self.locator(page, selector)
        try:
            locator.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError:
            return None
        value = locator.inner_text().strip()
        return value or None

    def input_value(self, page: object, selector: str) -> str | None:
        locator = self.locator(page, selector)
        try:
            locator.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError:
            return None
        value = locator.input_value().strip()
        return value or None

    def attribute_value(self, page: object, selector: str, attribute_name: str) -> str | None:
        locator = self.locator(page, selector)
        try:
            locator.wait_for(state="attached", timeout=10000)
        except PlaywrightTimeoutError:
            return None
        value = locator.get_attribute(attribute_name)
        if value is None:
            return None
        value = value.strip()
        return value or None

    def wait_for_optional(self, page: object, selector: str | None, *, state: str = "visible", timeout: int = 10000) -> bool:
        if not selector:
            return False
        locator = self.locator(page, selector)
        try:
            locator.wait_for(state=state, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False


def _attach_page_logging(page: object, browser_log_path: Path) -> None:
    browser_log_path.parent.mkdir(parents=True, exist_ok=True)
    browser_log_path.write_text("", encoding="utf-8")

    def write_line(message: str) -> None:
        with browser_log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    page.on("console", lambda msg: write_line(f"console:{msg.type}: {msg.text}"))
    page.on("pageerror", lambda err: write_line(f"pageerror: {err}"))
    page.on("requestfailed", lambda request: write_line(f"requestfailed: {request.method} {request.url}"))


def _equivalent_number_text(left: str, right: str) -> bool:
    normalize = lambda value: value.strip().replace(",", ".")
    return normalize(left) == normalize(right)
