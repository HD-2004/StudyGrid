r"""Browser check of the full StudyGrid flow. Requires both servers running.

Run: .venv\Scripts\python.exe scripts\smoke_ui.py
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "artifacts"
OUT.mkdir(exist_ok=True)

errors: list[str] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto("http://localhost:5173", wait_until="domcontentloaded")
    page.wait_for_selector("h1")
    assert "Create your study schedule" in page.inner_text("h1")
    assert page.locator(".empty-calendar-overlay").is_visible()
    print("[ok] empty calendar is interactive on first load")

    page.locator(".empty-calendar-overlay").get_by_role(
        "button", name="Create study plan"
    ).click()
    dialog = page.get_by_role("dialog", name="Create study plan")
    dialog.wait_for()

    assert page.locator("text=Study time each day").count() == 1
    assert page.input_value("#day-0") == "2", "daily capacity should be shown in hours"
    assert "12.0 weekly hours" in dialog.inner_text()
    assert page.input_value("#session-length") == "60"
    assert page.locator("#session-length option").count() == 5
    assert page.input_value("#long-break") == "45"

    page.select_option("#session-length", "custom")
    page.wait_for_selector("#custom-session-length")
    page.fill("#custom-session-length", "75")
    assert "8 minutes of rest" in dialog.inner_text()
    page.select_option("#session-length", "60")

    dialog.get_by_label("Subject").first.fill("Linear Algebra")
    material = dialog.get_by_label("Or paste a syllabus, notes, or topic outline").first
    material.fill(
        "Vector spaces\nMatrix transformations\nEigenvalues and eigenvectors\nLeast squares"
    )
    dialog.get_by_role("button", name="Analyze pasted text").first.click()
    dialog.locator(".analysis-source").wait_for(timeout=30_000)
    source = dialog.locator(".analysis-source").inner_text()
    assert source in {"OpenAI analysis", "Offline fallback"}
    print(f"[ok] material analysis source is visible: {source}")

    dialog.locator(".planner-drawer").evaluate("element => { element.scrollTop = 0 }")
    page.screenshot(path=str(OUT / "01-intake.png"), full_page=True)

    dialog.get_by_role("button", name="Generate study plan").click()
    page.wait_for_selector(".sx__event", timeout=20_000)
    events = page.locator(".sx__event").count()
    assert events > 0
    visible_event_text = " ".join(page.locator(".sx__event").all_inner_texts())
    assert "9:00 AM" in visible_event_text
    assert "2:00 AM" not in visible_event_text
    page.screenshot(path=str(OUT / "02-calendar.png"), full_page=True)
    print(f"[ok] plan built with {events} visible events and local time preserved")

    summary_values = page.locator(".summary dd").all_inner_texts()
    assert len(summary_values) == 3
    total_before = int(summary_values[0]) + int(summary_values[1])

    page.fill("#coach-input", "What should I study next?")
    page.locator(".coach button[type='submit']").click()
    page.locator(".source").wait_for(timeout=20_000)
    coach_message = page.locator(".coach-message.assistant").last
    coach_reply = coach_message.locator("p").inner_text().strip()
    coach_source = page.locator(".source").inner_text()
    assert coach_message.locator("span").inner_text() == "Coach"
    assert len(coach_reply) >= 20
    assert coach_source in {"AI guidance", "Offline guidance"}
    print(f"[ok] plan-aware coach replied: {' '.join(coach_reply.split())[:72]}")

    learn = page.locator(".sx__event.sg-learn").count()
    assert learn > 0
    learn_color = page.locator(".sx__event.sg-learn").first.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    review = 0
    for _ in range(4):
        page.get_by_role("button", name="Next period").click()
        page.wait_for_timeout(350)
        review = page.locator(".sx__event.sg-review").count()
        if review:
            break
    assert review > 0
    review_color = page.locator(".sx__event.sg-review").first.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert learn_color != review_color
    page.screenshot(path=str(OUT / "02b-reviews.png"), full_page=True)
    print(f"[ok] {learn} first passes and {review} later reviews are visually distinct")

    page.get_by_role("button", name="Today").click()
    page.wait_for_timeout(350)
    page.locator(".sx__event").first.click()
    page.locator(".session-detail").wait_for()
    page.select_option("#completion", "completed")
    page.select_option("#recall", "poor")
    page.get_by_role("button", name="Save and update plan").click()
    page.get_by_role("heading", name="Where your week went").wait_for(timeout=15_000)
    page.get_by_text("Synced from study progress").first.wait_for(timeout=10_000)
    page.select_option("#activity-category", "unexpected")
    page.fill("#activity-label", "Urgent family task")
    page.fill("#activity-duration", "90")
    page.get_by_role("button", name="Log activity", exact=True).click()
    page.get_by_text("Urgent family task").wait_for(timeout=10_000)
    page.screenshot(path=str(OUT / "03-progress.png"), full_page=True)
    print("[ok] Progress chart combines synced study time and a manual activity")
    page.get_by_role("button", name="Return to calendar").click()
    page.get_by_role("heading", name="What changed").wait_for(timeout=15_000)

    changed = page.locator("section:has-text('What changed')").inner_text()
    assert "recall" in changed.lower()
    adapted_values = page.locator(".summary dd").all_inner_texts()
    total_after = int(adapted_values[0]) + int(adapted_values[1])
    assert total_after > 0
    page.screenshot(path=str(OUT / "03-adapted.png"), full_page=True)
    print(f"[ok] adaptive review explained: {total_before} -> {total_after} sessions")

    page.locator(".sx__event").nth(1).click()
    page.select_option("#completion", "not_completed")
    page.get_by_text("What came up instead?").wait_for()
    chips = page.locator(".chip")
    assert chips.count() >= 6
    club_reason = page.get_by_role("button", name="Club meeting", exact=True)
    club_reason.click()
    assert club_reason.get_attribute("aria-pressed") == "true"
    page.get_by_role("button", name="Save and update plan").click()
    page.get_by_role("heading", name="Where your week went").wait_for(timeout=10_000)
    page.get_by_role("button", name="Return to calendar").click()
    insights_heading = page.get_by_role("heading", name="Where your time went")
    insights_heading.wait_for(timeout=10_000)
    panel = insights_heading.locator("..").inner_text()
    assert "Club meeting" in panel and "lost" in panel
    page.screenshot(path=str(OUT / "05-insights.png"), full_page=True)
    print("[ok] missed session is rescheduled and attributed in insights")

    page.get_by_role("button", name="Start a new plan").click()
    dialog.wait_for()
    dialog.get_by_label("Subject").first.fill("Intensive Physics")
    tomorrow = page.evaluate(
        "new Date(Date.now() + 86400000).toISOString().slice(0, 10)"
    )
    dialog.get_by_label("Exam").first.fill(tomorrow)
    dialog.get_by_label("Topic 1 name").first.fill("Ten chapter review")
    dialog.get_by_label("Minutes for Ten chapter review").fill("600")
    for index in range(7):
        dialog.locator(f"#day-{index}").fill("0.5")
    dialog.get_by_role("button", name="Generate study plan").click()
    dialog.wait_for(state="detached", timeout=15_000)
    assert "No room before the exam" in page.inner_text("body")
    page.screenshot(path=str(OUT / "04-exam-rush.png"), full_page=True)
    print("[ok] custom over-capacity window reports work that does not fit")

    page.get_by_role("button", name="Delete my data").click()
    page.get_by_role("button", name="Confirm delete all").click()
    page.locator(".empty-calendar-overlay").wait_for()
    print("[ok] delete-my-data clears the persisted browser session")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("http://localhost:5173", wait_until="domcontentloaded")
    page.get_by_role("button", name="Switch to dark theme").click()
    assert page.locator("html").get_attribute("data-theme") == "dark"
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    page.locator(".empty-calendar-overlay").get_by_role(
        "button", name="Create study plan"
    ).click()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    page.screenshot(path=str(OUT / "06-mobile.png"), full_page=True)
    print("[ok] dark theme and setup fit a 390px mobile viewport")

    browser.close()

if errors:
    print("\nconsole errors:")
    for error in errors:
        print(" ", error)
    sys.exit(1)

print(f"\nui smoke passed, screenshots in {OUT}")
