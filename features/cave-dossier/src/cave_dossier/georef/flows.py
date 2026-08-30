"""The point-georeferencing flow — ported near-verbatim from
crospeleo-automation ``georef/flows.py`` (see docs/PORTING.md).
Only the imports changed; every timing calibration and retry lesson
(the 45 s record wait, the marker-click popup retrigger, the
marker-centered crop — landscape 5:4 over the near vicinity since
2026-08-30, originally square) is kept exactly as learned over there."""

from __future__ import annotations

import logging
import os
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from cave_dossier.georef.artifacts import save_debug_screenshot
from cave_dossier.georef.client import GeorefClient
from cave_dossier.georef.models import GeorefArtifacts, GeorefInput, GeorefResult, GeorefSession, GeorefStatus
from cave_dossier.georef.selectors import SelectorRegistry

LOGGER = logging.getLogger(__name__)
_DEBUG_COPY = os.environ.get("GEOREF_DEBUG_COPY") == "1"

# Delivery budget for the excerpt PNG (user, 2026-08-29): as much map as
# fits under 1 MB.  The capture window is oversized on purpose (see
# client.py), so the guard downscales in 15 % steps only if the encoded
# PNG actually overshoots.
MAX_EXCERPT_BYTES = 1_000_000
_MIN_EXCERPT_SIDE = 512


def _diag(msg: str) -> None:
    if _DEBUG_COPY:
        print(f"[georef-copy-diag] {msg}", file=sys.stderr, flush=True)


def run_point_georef_flow(
    client: GeorefClient,
    session: GeorefSession,
    georef_input: GeorefInput,
    selectors: dict[str, str],
    artifacts: GeorefArtifacts,
) -> GeorefResult:
    registry = SelectorRegistry(selectors)
    page = session.page
    warnings = list(georef_input.notes)
    debug_screenshots: list[str] = []
    debug_enabled = bool(getattr(client, "debug", False))

    def _shot(name: str) -> None:
        if debug_enabled:
            debug_screenshots.append(str(save_debug_screenshot(page, artifacts.debug_dir / name)))

    try:
        map_switch_selector = registry.optional("georef_map_switch_tk25")
        if map_switch_selector:
            client.click(page, map_switch_selector, optional=True)
            _shot("map_switched_tk25.png")

        _open_tools_menu(client, page, registry)
        _shot("tools_menu_opened.png")

        coordinate_tool_selector = registry.optional("georef_coordinate_tool_link") or registry.require("georef_point_tool")
        client.click(page, coordinate_tool_selector)
        _shot("coordinate_tool_opened.png")

        tool_ready_selector = registry.optional("georef_coordinate_form_ready")
        if tool_ready_selector:
            client.wait_for_optional(page, tool_ready_selector, timeout=10000)

        _fill_locality(client, page, registry, georef_input.object_name)

        projection_selector = registry.optional("georef_projection_select")
        projection_value = registry.optional("georef_projection_value")
        if projection_selector and projection_value:
            page.locator(projection_selector).first.select_option(label=projection_value)

        uncertainty_selector = registry.optional("georef_uncertainty_input")
        uncertainty_value = registry.optional("georef_uncertainty_value")
        if uncertainty_selector and uncertainty_value:
            client.fill(page, uncertainty_selector, uncertainty_value)

        client.fill_with_fallback(page, registry.require("georef_x_htrs_input"), georef_input.x_input_variants)
        client.fill_with_fallback(page, registry.require("georef_y_htrs_input"), georef_input.y_input_variants)
        _shot("coordinates_entered.png")

        validate_selector = registry.optional("georef_validate_button")
        if validate_selector:
            client.click(page, validate_selector, optional=True)

        save_selector = registry.require("georef_save_button")
        client.click(page, save_selector)
        page.wait_for_timeout(client.settings.georef_post_save_wait_ms)
        _shot("location_saved.png")

        copied_record = _copy_georef_record(client, page, registry, warnings)
        if not copied_record:
            warnings.append("Georef record could not be copied from the identification popup.")

        close_popup_selector = registry.optional("georef_close_popup_button")
        if close_popup_selector:
            client.click(page, close_popup_selector, optional=True)
            page.wait_for_timeout(1000)

        _wait_for_tk25_tiles(page, timeout_ms=20000)
        page.wait_for_timeout(1500)

        _save_marker_centered_map(page, artifacts)

        return GeorefResult(
            success=bool(copied_record),
            georef_record=copied_record,
            georef_status=GeorefStatus.READY if copied_record else GeorefStatus.WARNING,
            warnings=warnings,
            debug_screenshots=debug_screenshots,
            map_screenshot_path=str(artifacts.map_screenshot_path),
            trace_path=str(artifacts.trace_path),
            browser_log_path=str(artifacts.browser_log_path),
        )
    except Exception as exc:
        error_path = artifacts.debug_dir / "flow_error.png"
        debug_screenshots.append(str(save_debug_screenshot(page, error_path)))
        return GeorefResult(
            success=False,
            georef_status=GeorefStatus.ERROR,
            warnings=warnings,
            debug_screenshots=debug_screenshots,
            map_screenshot_path=str(artifacts.map_screenshot_path) if artifacts.map_screenshot_path.exists() else None,
            trace_path=str(artifacts.trace_path),
            browser_log_path=str(artifacts.browser_log_path),
            error_message=str(exc),
        )


def _copy_georef_record(client: GeorefClient, page: object, registry: SelectorRegistry, warnings: list[str]) -> str | None:
    popup_trigger = registry.optional("georef_identification_popup_trigger")
    if popup_trigger:
        client.click(page, popup_trigger, optional=True)

    popup_ready = registry.optional("georef_identification_popup")
    if popup_ready:
        client.wait_for_optional(page, popup_ready, timeout=10000)

    copy_button = registry.optional("georef_copy_record_button")
    if copy_button:
        attribute_name = registry.optional("georef_copy_record_attribute")
        if attribute_name:
            if _DEBUG_COPY:
                _dump_copy_state(page, copy_button, attribute_name, label="pre-read")
            # Attempt 1: popup-auto-render path with a generous timeout.
            # Trace evidence (crospeleo object 613, 2026-05-12): the popup
            # CONTAINER rendered fast (#localityCopy attached within 1 s)
            # but the server took >30 s to populate `data-clipboard-text`.
            # The Georef site is just slow — a 10 s wait was the actual
            # bug, not the popup logic.
            record = _wait_for_populated_attribute(page, copy_button, attribute_name, timeout_ms=45000)

            # Attempt 2: re-wait once more.  Caught by the rare case
            # where the server takes longer than 45 s.  Read-only.
            if not record:
                LOGGER.warning(
                    "COPY_RETRY: attempt 1 (45 s) found no record; re-waiting (server unusually slow)"
                )
                record = _wait_for_populated_attribute(page, copy_button, attribute_name, timeout_ms=15000)

            # Attempt 3: click the map marker to manually re-trigger
            # the identification popup.  The save is already committed
            # server-side (map_screenshot proves the pin rendered);
            # this just re-opens the popup.  Idempotent — no new georef
            # IDs are allocated.
            if not record:
                LOGGER.warning(
                    "COPY_RETRY: attempt 2 still empty; clicking marker to re-trigger identification popup"
                )
                if _click_marker_to_retrigger_popup(page):
                    page.wait_for_timeout(800)
                    record = _wait_for_populated_attribute(page, copy_button, attribute_name, timeout_ms=15000)
                else:
                    LOGGER.warning("COPY_RETRY: no marker element found to click")

            if _DEBUG_COPY:
                _dump_copy_state(page, copy_button, attribute_name, label="post-wait")
            if record:
                client.click(page, copy_button, optional=True)
                page.wait_for_timeout(1000)
                return record
        client.click(page, copy_button, optional=True)
        page.wait_for_timeout(1000)

    record_selector = registry.optional("georef_record_value")
    if record_selector:
        record = client.text_content(page, record_selector) or client.input_value(page, record_selector)
        if record:
            return record

    clipboard = _read_clipboard(page)
    if clipboard:
        return clipboard

    warnings.append("Clipboard read did not return a Georef record.")
    return None


def _wait_for_populated_attribute(page: object, selector: str, attribute_name: str, *, timeout_ms: int) -> str | None:
    """Wait until `selector` has a non-empty `attribute_name`, then return its trimmed value.

    Waiting only for the element to be attached and then reading the
    attribute synchronously races against the Georef popup's JS that sets
    `data-clipboard-text` *after* mounting the button.  Headed mode masked
    the race; headless hit it intermittently.
    """
    try:
        page.wait_for_function(
            """([sel, attr]) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                const v = el.getAttribute(attr);
                return !!(v && v.trim());
            }""",
            arg=[selector, attribute_name],
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError:
        _diag(f"wait_for_populated_attribute: timeout after {timeout_ms}ms (selector={selector!r} attr={attribute_name!r})")
        return None
    try:
        value = page.locator(selector).first.get_attribute(attribute_name)
    except Exception as exc:  # noqa: BLE001
        _diag(f"wait_for_populated_attribute: read after wait failed: {exc!r}")
        return None
    return value.strip() if value else None


def _click_marker_to_retrigger_popup(page: object) -> bool:
    """Click the map marker via JS to manually trigger the identification popup.

    Used as a fallback when the post-save popup didn't auto-render
    (intermittent headless flake on the Georef server side).  The save
    is already committed — the map screenshot saved afterward proves the
    pin is on the map.  This call only re-opens the popup; it does NOT
    re-save and therefore does NOT allocate a new server-side georef ID.

    Returns True if a marker element was found and the click was
    dispatched, False otherwise.  Mirrors the marker-detection
    selectors used in `_save_marker_centered_map` so we hit the same
    element regardless of which renderer (OpenLayers / Leaflet) is
    live.  Dispatches mousedown / mouseup / click — some map libraries
    listen on the down/up pair rather than the synthetic click.
    """
    try:
        clicked = page.evaluate(
            """() => {
                const marker =
                    document.querySelector("img[src*='marker']") ||
                    document.querySelector("img[src*='pin']") ||
                    document.querySelector(".olAlphaImg") ||
                    document.querySelector("img[style*='z-index']");
                if (!marker) return false;
                const rect = marker.getBoundingClientRect();
                const cx = rect.x + rect.width / 2;
                const cy = rect.y + rect.height / 2;
                for (const type of ['mousedown', 'mouseup', 'click']) {
                    marker.dispatchEvent(new MouseEvent(type, {
                        bubbles: true, cancelable: true, view: window,
                        clientX: cx, clientY: cy, button: 0,
                    }));
                }
                return true;
            }"""
        )
        return bool(clicked)
    except Exception as exc:  # noqa: BLE001
        _diag(f"marker click failed: {exc!r}")
        return False


def _dump_copy_state(page: object, selector: str, attribute_name: str, *, label: str) -> None:
    """Print viewport, focus, popup presence, and outer HTML around the copy button."""
    try:
        viewport = page.viewport_size
    except Exception as exc:  # noqa: BLE001
        viewport = f"<error: {exc!r}>"
    try:
        has_focus = page.evaluate("() => document.hasFocus()")
    except Exception as exc:  # noqa: BLE001
        has_focus = f"<error: {exc!r}>"
    try:
        inner_size = page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio})")
    except Exception as exc:  # noqa: BLE001
        inner_size = f"<error: {exc!r}>"
    try:
        count = page.locator(selector).count()
    except Exception as exc:  # noqa: BLE001
        count = f"<error: {exc!r}>"
    try:
        attr_now = page.locator(selector).first.get_attribute(attribute_name) if count else None
    except Exception as exc:  # noqa: BLE001
        attr_now = f"<error: {exc!r}>"
    try:
        outer = page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const host = el.closest('.popup, .modal, .ol-popup, .leaflet-popup, [class*=popup], [class*=modal]') || el.parentElement;
                return (host || el).outerHTML.slice(0, 1200);
            }""",
            selector,
        )
    except Exception as exc:  # noqa: BLE001
        outer = f"<error: {exc!r}>"
    _diag(f"[{label}] viewport={viewport} innerSize={inner_size} hasFocus={has_focus}")
    _diag(f"[{label}] selector={selector!r} count={count} attr={attr_now!r}")
    _diag(f"[{label}] outerHTML(<=1200)={outer!r}")


def _read_clipboard(page: object) -> str | None:
    try:
        clipboard_value = page.evaluate(
            """async () => {
                try {
                    return (await navigator.clipboard.readText()) || '';
                } catch (error) {
                    return '';
                }
            }"""
        )
    except PlaywrightTimeoutError:
        return None

    cleaned = clipboard_value.strip()
    return cleaned or None


def _open_tools_menu(client: GeorefClient, page: object, registry: SelectorRegistry) -> None:
    coordinate_tool_selector = registry.optional("georef_coordinate_tool_link")
    if not coordinate_tool_selector:
        return
    opener = page.get_by_text("Osnovni alati za georeferenciranje", exact=False).first
    opener.wait_for(state="visible", timeout=15000)
    opener.click()
    if client.wait_for_optional(page, coordinate_tool_selector, timeout=5000):
        return
    opener.hover()
    page.locator(coordinate_tool_selector).first.wait_for(state="visible", timeout=5000)


def _fill_locality(client: GeorefClient, page: object, registry: SelectorRegistry, locality_value: str | None) -> None:
    if not locality_value:
        return
    locality_selector = registry.optional("georef_locality_input")
    if locality_selector:
        try:
            client.fill(page, locality_selector, locality_value)
            return
        except PlaywrightTimeoutError:
            pass
    page.get_by_role("textbox", name="Naziv lokaliteta").first.fill(locality_value)


def _wait_for_tk25_tiles(page: object, timeout_ms: int = 15000) -> None:
    page.wait_for_function(
        """() => {
            const tiles = Array.from(document.querySelectorAll("img.olTileImage[src*='layers=tk:TK25']"));
            if (!tiles.length) {
                return false;
            }
            const visibleTiles = tiles.filter(tile => {
                const style = window.getComputedStyle(tile);
                const rect = tile.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            });
            if (!visibleTiles.length) {
                return false;
            }
            return visibleTiles.every(tile => tile.complete && tile.naturalWidth > 0);
        }""",
        timeout=timeout_ms,
    )


def _save_marker_centered_map(page: object, artifacts: GeorefArtifacts) -> None:
    clip = page.evaluate(
        """() => {
            const marker =
                document.querySelector("img[src*='marker']") ||
                document.querySelector("img[src*='pin']") ||
                document.querySelector(".olAlphaImg") ||
                document.querySelector("img[style*='z-index']");
            if (!marker) {
                return null;
            }
            const rect = marker.getBoundingClientRect();
            // Map markers anchor at the bottom-center of their icon
            // (the pin's tip).  Centering on the geometric middle of
            // the icon rect would offset the captured area upward by
            // ~half the icon height; bias Y to the anchor instead so
            // the pin's actual location sits at frame center.
            const centerX = rect.x + (rect.width / 2);
            const anchorY = rect.y + (rect.height * 0.9);

            // Map area extents inside the page.  Right panel is 335px
            // wide, top header ~110px, bottom strip ~36px.  Left has a
            // narrow tool column starting at ~46px.
            const leftInset = 46;
            const topInset = 110;
            const rightLimit = window.innerWidth - 335;
            const bottomLimit = window.innerHeight - 36;
            const mapWidth = Math.max(0, rightLimit - leftInset);
            const mapHeight = Math.max(0, bottomLimit - topInset);

            // Landscape 5:4 crop of the cave's NEAR vicinity (user,
            // 2026-08-30 — replaces the original square crop, which read
            // as ~2.5 km in every direction and, being 1:1, blew up the
            // OSZ frame's height).  heightFactor 0.42 keeps roughly
            // 1.5 km above and below the entrance at the default-window
            // TK25 view (0.7 covered ~2.5 km, scaled by 1.5/2.5), and
            // the width follows the 5:4 aspect.  Shrinks automatically
            // on small windows.
            const heightFactor = 0.42;
            let cropH = Math.max(0, Math.floor(Math.min(mapWidth, mapHeight) * heightFactor));
            let cropW = Math.floor(cropH * 5 / 4);
            if (cropW > mapWidth) {
                cropW = mapWidth;
                cropH = Math.floor(cropW * 4 / 5);
            }

            // True-center on the marker anchor, then clamp so the
            // box stays within the map area.  The tight box leaves
            // slack on every side, so the clamp rarely fires and the
            // pin stays centered; near a map edge the clamp still
            // pushes the box inward (expected, unavoidable without
            // scrolling the map).
            let x = centerX - (cropW / 2);
            let y = anchorY - (cropH / 2);
            x = Math.max(leftInset, Math.min(x, rightLimit - cropW));
            y = Math.max(topInset, Math.min(y, bottomLimit - cropH));

            return {
                x: Math.max(0, x),
                y: Math.max(0, y),
                width: cropW,
                height: cropH,
                // Pixel ratio so the Python-side crop can scale CSS
                // pixel coords to screenshot pixel coords on HiDPI
                // displays.  page.screenshot() captures at the
                // browser's native DPR; getBoundingClientRect() and
                // window.innerWidth/Height are in CSS pixels.
                dpr: window.devicePixelRatio || 1,
            };
        }"""
    )
    if not clip:
        raise RuntimeError("Could not determine marker-centered crop bounds for the map screenshot.")
    _set_overlay_visibility(page, visible=False)
    try:
        # Capture the full viewport (no `clip` argument).  Playwright's
        # `clip` parameter triggers `captureBeyondViewport` under the
        # hood which applies a brief CDP device-metrics override —
        # visible as a sub-second page flicker.  Capturing the plain
        # viewport and cropping in Python sidesteps that entirely.
        png_bytes = page.screenshot()
        image = Image.open(BytesIO(png_bytes))
        dpr = float(clip.get("dpr") or 1.0)
        left = int(clip["x"] * dpr)
        top = int(clip["y"] * dpr)
        right = int((clip["x"] + clip["width"]) * dpr)
        bottom = int((clip["y"] + clip["height"]) * dpr)
        save_png_under_limit(image.crop((left, top, right, bottom)), artifacts.map_screenshot_path)
    finally:
        _set_overlay_visibility(page, visible=True)


def save_png_under_limit(image: Image.Image, path, *, max_bytes: int = MAX_EXCERPT_BYTES) -> None:
    """Write `image` as a PNG that fits `max_bytes`, sacrificing color depth
    before pixels.

    At each size: try truecolor first; if too big, try a 256-color adaptive
    palette — the TK25 scan has few colors, so quantizing costs almost
    nothing visually and compresses ~2-3× better, which is what lets the
    full-window capture (~1000 px) stay under the budget where truecolor
    would have to shrink to ~600 px.  Only when even the palette PNG
    overshoots does the image lose 15 % of its side and retry.  The floor at
    `_MIN_EXCERPT_SIDE` px guards against a pathological spiral (e.g. an
    incompressible screenshot); below it the last attempt is written as-is.
    """
    current = image
    while True:
        last = None
        for candidate in (current, _quantize_keeping_marker_red(current)):
            buffer = BytesIO()
            candidate.save(buffer, format="PNG", optimize=True)
            last = buffer
            if buffer.tell() <= max_bytes:
                Path(str(path)).write_bytes(buffer.getvalue())
                return
        if min(current.size) <= _MIN_EXCERPT_SIDE:
            Path(str(path)).write_bytes(last.getvalue())
            return
        current = current.resize(
            (int(current.width * 0.85), int(current.height * 0.85)),
            Image.LANCZOS,
        )


def _quantize_keeping_marker_red(image: Image.Image) -> Image.Image:
    """256-color adaptive palette that cannot lose the red map pin.

    A naive `quantize(colors=256)` merges the pin into the surroundings —
    it is a few hundred red pixels against a million map pixels, so
    median-cut spends no palette entry on it (seen live 2026-08-30: the
    pin came out green-grey).  So: quantize to 255 colors, reserve the
    256th palette slot for the marker's own mean red, and re-stamp every
    strongly-red source pixel onto that slot.
    """
    import numpy

    rgb = image.convert("RGB")
    quantized = rgb.quantize(colors=255)

    source = numpy.asarray(rgb, dtype=numpy.int16)
    r, g, b = source[..., 0], source[..., 1], source[..., 2]
    marker_mask = (r > 140) & (r - g > 50) & (r - b > 50)
    if not marker_mask.any():
        return quantized

    marker_color = source[marker_mask].mean(axis=0).astype(int)
    indexed = numpy.asarray(quantized, dtype=numpy.uint8).copy()
    indexed[marker_mask] = 255

    palette = quantized.getpalette()
    palette = (palette + [0] * 768)[:768]
    palette[765:768] = [int(marker_color[0]), int(marker_color[1]), int(marker_color[2])]

    result = Image.fromarray(indexed, mode="P")
    result.putpalette(palette)
    return result


def _set_overlay_visibility(page: object, *, visible: bool) -> None:
    if visible:
        page.locator(".leaflet-control-container").evaluate_all(
            """elements => {
                for (const element of elements) {
                    if ('prevDisplay' in element.dataset) {
                        element.style.display = element.dataset.prevDisplay;
                    }
                }
            }"""
        )
        return
    page.locator(".leaflet-control-container").evaluate_all(
        """elements => {
            for (const element of elements) {
                element.dataset.prevDisplay = element.style.display;
                element.style.display = 'none';
            }
        }"""
    )
