"""Browser Automation Tool - hardened for LLM agents"""

from typing import Optional, Literal, Dict, Any, List
from pathlib import Path
import logging
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError as PWTimeoutError

from agent.tools.base_tool import BaseTool, ToolResult
from agent.config import settings

logger = logging.getLogger(__name__)


class BrowserTool(BaseTool):
    """Browser automation using Playwright (hardened version with persistent context)"""

    def __init__(self, default_timeout: int = 10000):
        super().__init__(
            name="browser",
            description="Automate web browser actions: navigation, click, fill, read text, screenshot"
        )
        self.playwright = None
        self.browser: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.default_timeout = default_timeout
        
        # Persistent profile directory for saved sessions
        self.profile_dir = Path(settings.WORKSPACE_DIR) / "playwright_profile"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def start(self):
        """Start browser with persistent context (saves logins across sessions)."""
        if self.playwright and self.browser and self.page:
            return

        self.playwright = await async_playwright().start()
        
        # Use persistent context so logins persist
        self.browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 720},
            accept_downloads=True,
        )
        
        # Get existing page or create new one
        if self.browser.pages:
            self.page = self.browser.pages[0]
        else:
            self.page = await self.browser.new_page()
            
        self.page.set_default_timeout(self.default_timeout)
        logger.info(f"Browser started with persistent profile: {self.profile_dir}")

    async def stop(self):
        """Stop browser (profile is saved automatically)."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        self.page = None
        logger.info("Browser stopped")

    async def _ensure_page(self):
        """Ensure page exists and is usable."""
        if not self.browser or not self.page:
            await self.start()

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute browser action with structured error handling."""
        await self._ensure_page()

        try:
            if action == "goto":
                return await self.goto(**kwargs)
            elif action == "click":
                return await self.click_element(**kwargs)
            elif action == "click_link":
                return await self.click_link(**kwargs)
            elif action == "fill":
                return await self.fill_input(**kwargs)
            elif action == "get_text":
                return await self.get_text(**kwargs)
            elif action == "get_links":
                return await self.get_links(**kwargs)
            elif action == "screenshot":
                return await self.screenshot(**kwargs)
            elif action == "wait":
                return await self.wait_for_element(**kwargs)
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action: {action}")
        except PWTimeoutError as e:
            logger.warning(f"Browser timeout on {action}: {e}")
            return ToolResult(success=False, output=None, error=f"timeout: {str(e)[:200]}")
        except Exception as e:
            logger.error(f"Browser error during {action}: {e}", exc_info=True)
            return ToolResult(success=False, output=None, error=f"exception: {str(e)[:200]}")

    # -------- navigation --------

    async def goto(self, url: str, wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load") -> ToolResult:
        """Navigate to URL and wait until page is ready."""
        await self.page.goto(url, wait_until=wait_until)
        logger.info(f"Navigated to {url} (wait_until={wait_until})")
        return ToolResult(success=True, output=f"Loaded {url}")

    # -------- DOM extraction --------

    async def get_links(self, max_links: int = 10) -> ToolResult:
        """
        Extract clickable links from current page.
        Returns list of {text, url} for the LLM to choose from.
        """
        try:
            # Get all visible links with text
            links = await self.page.evaluate("""
                () => {
                    const allLinks = Array.from(document.querySelectorAll('a[href]'));
                    return allLinks
                        .filter(link => {
                            const rect = link.getBoundingClientRect();
                            const text = link.textContent.trim();
                            return rect.width > 0 && rect.height > 0 && text.length > 0;
                        })
                        .slice(0, 30)
                        .map((link, index) => ({
                            index: index,
                            text: link.textContent.trim().substring(0, 100),
                            url: link.href,
                        }));
                }
            """)
            
            result = {"links": links[:max_links], "count": len(links)}
            logger.info(f"Extracted {len(links)} links from page")
            return ToolResult(success=True, output=result)
        except Exception as e:
            logger.error(f"Failed to extract links: {e}")
            return ToolResult(success=False, output=None, error=f"exception: {str(e)[:200]}")

    # -------- locators and actions --------

    async def click_link(self, index: Optional[int] = None, text_contains: Optional[str] = None) -> ToolResult:
        """
        Click a link by index (from get_links) or by partial text match.
        This is more reliable than CSS selectors for search results.
        """
        try:
            if index is not None:
                # Click by index
                clicked = await self.page.evaluate(f"""
                    () => {{
                        const links = Array.from(document.querySelectorAll('a[href]'))
                            .filter(link => {{
                                const rect = link.getBoundingClientRect();
                                const text = link.textContent.trim();
                                return rect.width > 0 && rect.height > 0 && text.length > 0;
                            }});
                        if (links[{index}]) {{
                            links[{index}].click();
                            return true;
                        }}
                        return false;
                    }}
                """)
                
                if clicked:
                    await self.page.wait_for_load_state("load", timeout=5000)
                    logger.info(f"Clicked link at index {index}")
                    return ToolResult(success=True, output=f"Clicked link {index}")
                else:
                    return ToolResult(success=False, output=None, error=f"no_link_at_index: {index}")
            
            elif text_contains:
                # Click by text content
                locator = self.page.get_by_role("link", name=text_contains)
                await locator.first.click(timeout=5000)
                await self.page.wait_for_load_state("load", timeout=5000)
                logger.info(f"Clicked link containing text: {text_contains}")
                return ToolResult(success=True, output=f"Clicked link with text '{text_contains}'")
            
            else:
                return ToolResult(success=False, output=None, error="need_index_or_text")
                
        except PWTimeoutError:
            return ToolResult(success=False, output=None, error="timeout: link not found or not clickable")
        except Exception as e:
            logger.error(f"Failed to click link: {e}")
            return ToolResult(success=False, output=None, error=f"exception: {str(e)[:200]}")

    async def click_element(
        self,
        selector: str,
        description: Optional[str] = None,
        timeout: Optional[int] = None,
        state: Literal["visible", "attached"] = "visible",
        force: bool = False,
    ) -> ToolResult:
        """
        Click element with auto-wait and explicit pre-wait.
        Use this for buttons, not for links (use click_link instead).
        """
        timeout = timeout or self.default_timeout

        locator = self.page.locator(selector)
        await locator.wait_for(state=state, timeout=timeout)
        await locator.click(force=force)

        desc = description or selector
        logger.info(f"Clicked: {selector}")
        return ToolResult(success=True, output=f"Clicked {desc}")

    async def fill_input(
        self,
        selector: str,
        text: str,
        clear_first: bool = True,
        timeout: Optional[int] = None,
        state: Literal["visible", "attached"] = "visible",
    ) -> ToolResult:
        """Fill input field with text, waiting for it to be ready."""
        timeout = timeout or self.default_timeout

        locator = self.page.locator(selector)
        await locator.wait_for(state=state, timeout=timeout)

        if clear_first:
            await locator.fill("")

        await locator.fill(text)
        logger.info(f"Filled {selector} with text '{text[:40]}'")
        return ToolResult(success=True, output=f"Filled {selector}")

    async def get_text(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: Literal["visible", "attached"] = "visible",
        max_len: int = 5000,
    ) -> ToolResult:
        """Get element text with wait and size cap."""
        timeout = timeout or self.default_timeout
        locator = self.page.locator(selector)
        await locator.wait_for(state=state, timeout=timeout)
        text = await locator.text_content()
        if text is None:
            return ToolResult(success=False, output=None, error="no_text")

        trimmed = text[:max_len]
        return ToolResult(success=True, output=trimmed)

    async def screenshot(self, path: str, full_page: bool = True) -> ToolResult:
        """Take screenshot."""
        await self.page.screenshot(path=path, full_page=full_page)
        logger.info(f"Screenshot saved to {path}")
        return ToolResult(success=True, output=f"Screenshot saved to {path}")

    async def wait_for_element(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: Literal["visible", "attached", "hidden", "detached"] = "visible",
    ) -> ToolResult:
        """Wait for element selector to reach a certain state."""
        timeout = timeout or self.default_timeout
        locator = self.page.locator(selector)
        await locator.wait_for(state=state, timeout=timeout)
        return ToolResult(success=True, output=f"Element {selector} reached state={state}")

    def validate_params(self, **kwargs) -> bool:
        return True
