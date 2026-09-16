"""Browser check of the full flow. Requires both servers running.

Run: .venv\\Scripts\\python.exe scripts\\smoke_ui.py
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "artifacts"
OUT.mkdir(exist_ok=True)

errors: list[str] = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto("http://localhost:5173", wait_until="networkidle")
    assert "StudyGrid" in page.inner_text("h1"), "masthead missing"
    page.screenshot(path=str(OUT / "01-intake.png"), full_page=True)
    print("[ok] intake renders")

    # Build a plan from the default seed.
    page.click("text=Build my study plan")
    page.wait_for_selector(".sx__event", timeout=15000)
    events = page.locator(".sx__event").count()
    assert events > 0, "no calendar events rendered"
    page.screenshot(path=str(OUT / "02-calendar.png"), full_page=True)
    print(f"[ok] plan built, {events} events on the calendar")

    summary = page.inner_text(".summary")
    assert "first passes" in summary and "reviews" in summary
    print(f"[ok] summary: {' '.join(summary.split())[:70]}")

    # Plan-wide session tally, independent of which week is on screen.
    parts = summary.split()
    total_before = int(parts[0]) + int(parts[3])

    # Learn vs review must be visually distinct. The week view only shows the
    # current week, so reviews scheduled later are not in the DOM yet; check the
    # month view where the whole span is visible.
    learn = page.locator(".sx__event.sg-learn").count()
    assert learn > 0, "no first-pass events styled"

    review = 0
    for _ in range(4):
        page.click("button:has-text('Next period')")
        page.wait_for_timeout(500)
        review = page.locator(".sx__event.sg-review").count()
        if review:
            break
    assert review > 0, "no review events styled in any of the next four weeks"
    page.screenshot(path=str(OUT / "02b-reviews.png"), full_page=True)
    print(f"[ok] {learn} first passes this week, {review} reviews later, visually distinct")

    page.click("button:has-text('Today')")
    page.wait_for_timeout(500)

    # Click a session, report poor recall, confirm the plan responds and says how.
    page.locator(".sx__event").first.click()
    page.wait_for_selector("aside")
    print("[ok] session detail opens")

    page.select_option("#completion", "completed")
    page.select_option("#recall", "poor")
    page.click("text=Save and update plan")
    page.wait_for_selector("text=What changed", timeout=15000)

    changed = page.inner_text("section:has-text('What changed')")
    assert "recall" in changed.lower(), f"unexpected change text: {changed}"

    tally = page.inner_text(".summary").split()
    total_after = int(tally[0]) + int(tally[3])

    # Two legitimate outcomes: a review is added, or the calendar is genuinely
    # full and the app says so. Both must be reported, neither may be silent.
    if total_after == total_before + 1:
        print(f"[ok] adaptation added a review: {total_before} -> {total_after} sessions")
    else:
        assert "full" in changed.lower() or "too close" in changed.lower(), (
            f"session count unchanged but no explanation given: {changed}"
        )
        assert total_after == total_before, "session count changed unexpectedly"
        print("[ok] no room before the exam, and the app explains that instead of failing")

    page.screenshot(path=str(OUT / "03-adapted.png"), full_page=True)

    # A missed session must always move, never vanish. Reporting it also
    # exercises the 8.3 reason prompt.
    page.locator(".sx__event").nth(1).click()
    page.wait_for_selector("aside")
    page.select_option("#completion", "not_completed")

    # The reason chips must appear only for a session that did not happen.
    page.wait_for_selector("text=What came up instead?", timeout=5000)
    chips = page.locator(".chip")
    assert chips.count() >= 6, f"expected reason chips, found {chips.count()}"
    page.click(".chip:has-text('Club meeting')")
    assert page.locator(".chip.selected").count() == 1, "reason should toggle on"
    print(f"[ok] miss-reason prompt shows {chips.count()} options and selects")

    page.click("text=Save and update plan")
    page.wait_for_timeout(1500)
    moved_tally = page.inner_text(".summary").split()
    assert int(moved_tally[0]) + int(moved_tally[3]) == total_after, (
        "a missed session must be rescheduled, not dropped"
    )
    print("[ok] missed session rescheduled without loss")

    # Insights panel must appear and attribute the lost time (8.3).
    page.wait_for_selector("text=Where your time went", timeout=5000)
    panel = page.inner_text("section:has-text('Where your time went')")
    assert "Club meeting" in panel, f"reason not attributed: {panel}"
    assert "lost" in panel and "studied" in panel
    page.screenshot(path=str(OUT / "05-insights.png"), full_page=True)
    print(f"[ok] insights: {' '.join(panel.split())[:88]}")

    # A completed session must not ask why it was missed.
    page.locator(".sx__event").first.click()
    page.wait_for_selector("aside")
    page.select_option("#completion", "completed")
    page.wait_for_timeout(400)
    assert page.locator("text=What came up instead?").count() == 0, (
        "reason prompt should be hidden for a completed session"
    )
    print("[ok] reason prompt hidden when the session was completed")
    page.click("text=Close")

    # Exam rush should surface the honest "did not fit" message.
    page.click("text=Start a new plan")
    page.wait_for_selector("text=Build my study plan")
    page.click("text=Exam in three days")
    page.click("text=Build my study plan")
    page.wait_for_selector(".sx__event", timeout=15000)
    body = page.inner_text("body")
    assert "No room before the exam" in body, "over-capacity case not surfaced"
    page.screenshot(path=str(OUT / "04-exam-rush.png"), full_page=True)
    print("[ok] exam rush reports what did not fit")

    # The intake and generated plan must fit a phone viewport. This catches
    # fixed desktop widths and viewport metadata regressions.
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("http://localhost:5173", wait_until="networkidle")
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    ), "intake overflows the mobile viewport"
    page.click("text=Build my study plan")
    page.wait_for_selector(".sx__event", timeout=15000)
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    ), "calendar overflows the mobile viewport"
    page.screenshot(path=str(OUT / "06-mobile.png"), full_page=True)
    print("[ok] intake and calendar fit a 390px mobile viewport")

    browser.close()

if errors:
    print("\nconsole errors:")
    for e in errors:
        print(" ", e)
    sys.exit(1)

print(f"\nui smoke passed, screenshots in {OUT}")
