r"""Browser smoke check for the current StudyGrid calendar workspace.

Requires the API and web dev servers. Run:
.venv\Scripts\python.exe scripts\smoke_ui.py
"""

import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "artifacts"
OUT.mkdir(exist_ok=True)
BASE_URL = os.getenv("STUDYGRID_WEB_URL", "http://localhost:5173").rstrip("/")
errors: list[str] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.locator(".empty-calendar-overlay").get_by_role(
        "button", name="Create study plan"
    ).click()
    setup = page.get_by_role("dialog", name="Create study plan")
    setup.get_by_label("Subject").first.fill("Linear Algebra")
    setup.get_by_label("Topic 1 name").first.fill("Vector spaces")
    page.screenshot(path=str(OUT / "01-intake.png"), full_page=True)
    setup.get_by_role("button", name="Generate study plan").click()

    page.locator(".calendar-app").wait_for(timeout=20_000)
    assert page.locator(".sx__event").count() > 0
    assert page.locator("html").get_attribute("data-theme") == "dark"
    page.screenshot(path=str(OUT / "02-calendar.png"), full_page=True)
    print("[ok] dark weekly calendar renders persisted schedule events")

    first = page.locator(".sx__event").first
    first.click()
    detail = page.locator(".session-detail")
    detail.wait_for()
    assert detail.get_by_role("button", name="Pending", exact=True).get_attribute("aria-pressed") == "true"
    detail.get_by_role("button", name="Completed", exact=True).click()
    detail.get_by_label("Bạn nhớ nội dung ở mức nào?").select_option("well")
    detail.get_by_role("button", name="Xác nhận hoàn thành").click()
    page.get_by_role("button", name="Tiến độ", exact=True).click()
    page.get_by_role("heading", name="Where your week went").wait_for(timeout=15_000)
    page.get_by_text("Synced from study progress").first.wait_for()
    page.screenshot(path=str(OUT / "03-progress.png"), full_page=True)
    print("[ok] Completed status updates progress only when Progress is opened")

    page.get_by_role("button", name="Return to calendar").click()
    page.get_by_role("button", name="Tạo", exact=True).click()
    create = page.get_by_role("dialog", name="Thêm vào lịch")
    create.get_by_label("Tên công việc").fill("Demo rehearsal")
    create.get_by_label("Lịch / nhóm").fill("Capstone")
    create.get_by_label("Bắt đầu").fill("2026-09-17T18:00")
    create.get_by_label("Kết thúc").fill("2026-09-17T19:00")
    create.get_by_role("button", name="Tạo công việc").click()
    manual = page.get_by_role("button", name=re.compile("Capstone: Demo rehearsal"))
    manual.wait_for()
    manual.click()
    detail = page.locator(".session-detail")
    detail.get_by_role("button", name="Cancel", exact=True).click()
    detail.get_by_role("button", name="Unexpected work").click()
    detail.get_by_role("button", name="Xác nhận & dời lịch").click()
    detail.wait_for(state="detached", timeout=15_000)
    page.get_by_role("button", name="Tiến độ", exact=True).click()
    page.get_by_text("Cancelled & rescheduled").wait_for(timeout=15_000)
    page.screenshot(path=str(OUT / "05-insights.png"), full_page=True)
    print("[ok] Cancel requires a reason, reschedules, and syncs the dashboard")

    page.get_by_role("button", name="Return to calendar").click()
    page.get_by_role("button", name="Lập kế hoạch với AI").click()
    page.get_by_role("heading", name="Lập kế hoạch với AI").wait_for()
    page.wait_for_timeout(300)
    utility = page.locator(".utility-area").bounding_box()
    assert utility and utility["width"] >= 350, "AI panel should remain fully visible on desktop"
    page.get_by_role("button", name="Tạo đề xuất").click()
    preview = page.locator(".ai-preview")
    preview.wait_for(timeout=20_000)
    assert "Đề xuất" in preview.inner_text()
    preview.get_by_role("button", name="Áp dụng").click()
    preview.wait_for(state="detached", timeout=15_000)
    page.screenshot(path=str(OUT / "03-adapted.png"), full_page=True)
    print("[ok] AI planning previews a move and applies it only after confirmation")

    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    page.screenshot(path=str(OUT / "06-mobile.png"), full_page=True)
    print("[ok] calendar remains contained at 390px")

    browser.close()

if errors:
    print("\nconsole errors:")
    for error in errors:
        print(" ", error)
    sys.exit(1)

print(f"\nui smoke passed, screenshots in {OUT}")
