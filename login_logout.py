import os
import re
import sys
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


def must_get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def is_visible(locator):
    try:
        return locator.first.is_visible(timeout=1000)
    except Exception:
        return False


def get_text_if_visible(locator):
    try:
        if locator.first.is_visible(timeout=1000):
            return locator.first.inner_text(timeout=1000).strip()
    except Exception:
        pass
    return None


def main():
    load_dotenv()

    base_url = must_get_env("BASE_URL")
    username = must_get_env("USERNAME")
    password = must_get_env("PASSWORD")

    timeout_ms = int(os.getenv("TIMEOUT_MS", "180000"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            page.goto(base_url, wait_until="domcontentloaded")

            app = page.frame_locator('iframe[title="streamlitApp"]')

            email_input = app.locator('input[aria-label="Email"]').first
            pwd_input = app.locator('input[aria-label="Password"]').first
            sign_in_button = app.get_by_role("button", name=re.compile(r"^Sign in$", re.I)).first
            logout_button = app.get_by_role("button", name=re.compile(r"^Logout$", re.I)).first
            signed_in_text = app.get_by_text("Signed in as").first
            running_text = app.get_by_text("Running").first

            error_candidates = [
                app.get_by_text(re.compile(r"invalid", re.I)).first,
                app.get_by_text(re.compile(r"incorrect", re.I)).first,
                app.get_by_text(re.compile(r"wrong", re.I)).first,
                app.get_by_text(re.compile(r"failed", re.I)).first,
                app.get_by_text(re.compile(r"error", re.I)).first,
                app.get_by_text(re.compile(r"authentication", re.I)).first,
                app.get_by_text(re.compile(r"credential", re.I)).first,
            ]

            email_input.wait_for(state="visible", timeout=timeout_ms)
            pwd_input.wait_for(state="visible", timeout=timeout_ms)

            email_input.fill(username)
            pwd_input.fill(password)
            sign_in_button.click()

            page.wait_for_timeout(3000)

            login_ok = False

            for _ in range(45):
                if is_visible(signed_in_text) and is_visible(logout_button):
                    login_ok = True
                    break
                page.wait_for_timeout(1000)

            if not login_ok:
                still_on_login = is_visible(sign_in_button) and is_visible(email_input)
                running_visible = is_visible(running_text)
                logout_visible = is_visible(logout_button)
                signed_in_visible = is_visible(signed_in_text)

                detected_error = None
                for candidate in error_candidates:
                    detected_error = get_text_if_visible(candidate)
                    if detected_error:
                        break

                raise RuntimeError(
                    "Login verification failed. "
                    f"still_on_login={still_on_login}, "
                    f"running_visible={running_visible}, "
                    f"signed_in_visible={signed_in_visible}, "
                    f"logout_visible={logout_visible}, "
                    f"detected_error={detected_error!r}"
                )

            logout_button.click()
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
