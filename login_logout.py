import os
import re
import sys
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def must_get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def main() -> None:
    load_dotenv()

    base_url = must_get_env("BASE_URL")
    username = must_get_env("USERNAME")
    password = must_get_env("PASSWORD")

    timeout_ms = int(os.getenv("TIMEOUT_MS", "180000"))
    headless = os.getenv("HEADLESS", "1") != "0"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            # 1) Open the Streamlit share wrapper page
            page.goto(base_url, wait_until="domcontentloaded")

            # 2) Target the embedded app iframe
            app_frame = page.frame_locator('iframe[title="streamlitApp"]')

            # 3) Wait for login form INSIDE the iframe
            email_input = app_frame.locator('input[aria-label="Email"]').first
            pwd_input = app_frame.locator('input[aria-label="Password"]').first

            email_input.wait_for(state="visible", timeout=timeout_ms)
            pwd_input.wait_for(state="visible", timeout=timeout_ms)

            # 4) Login
            email_input.fill(username)
            pwd_input.fill(password)
            app_frame.get_by_role("button", name=re.compile(r"^Sign in$", re.I)).click()

            # 5) Verify logged in (sidebar text + Logout button inside iframe)
            try:
                app_frame.get_by_text("Signed in as").wait_for(state="visible", timeout=timeout_ms)
                app_frame.get_by_role("button", name=re.compile(r"^Logout$", re.I)).wait_for(
                    state="visible", timeout=timeout_ms
                )
            except PlaywrightTimeoutError:
                raise RuntimeError("Login verification failed (did not see 'Signed in as' and 'Logout').")

            # 6) Logout
            app_frame.get_by_role("button", name=re.compile(r"^Logout$", re.I)).click()

            # 7) Verify logged out (email field visible again)
            email_input = app_frame.locator('input[aria-label="Email"]').first
            email_input.wait_for(state="visible", timeout=timeout_ms)

            print("✅ Login and logout completed successfully.")

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Automation failed: {e}", file=sys.stderr)
        sys.exit(1)
