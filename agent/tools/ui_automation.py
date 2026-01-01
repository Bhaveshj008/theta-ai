"""UI Automation Tool using pywinauto for Windows Desktop Applications"""
import sys
import re
import logging
import asyncio
from typing import Optional, List, Dict, Any
from agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class UIAutomationTool(BaseTool):
    """Windows UI Automation using pywinauto - Generic for ANY app"""
    
    def __init__(self):
        super().__init__(
            name="ui_automation",
            description="Automate Windows desktop application UI elements"
        )
        self.platform = sys.platform
        self._app_connections: Dict[str, Any] = {}
        
    def _ensure_windows(self) -> bool:
        """Ensure we're on Windows"""
        if self.platform != "win32":
            return False
        try:
            import pywinauto
            return True
        except ImportError:
            logger.error("pywinauto not installed. Install with: pip install pywinauto")
            return False
    
    async def _get_app_connection(self, app_name: str, window_title: Optional[str] = None, 
                                  force_reconnect: bool = False) -> Optional[Any]:
        """Get or create connection to an application"""
        if not self._ensure_windows():
            return None
        
        try:
            from pywinauto import Application
            
            cache_key = f"{app_name}:{window_title or 'default'}"
            if not force_reconnect and cache_key in self._app_connections:
                try:
                    app = self._app_connections[cache_key]
                    _ = app.top_window()
                    return app
                except:
                    logger.debug(f"Cached connection stale, reconnecting...")
                    del self._app_connections[cache_key]
            
            # Try multiple connection methods
            process_map = {
                "camera": "WindowsCamera.exe",
                "notepad": "notepad.exe",
                "calculator": "Calculator.exe",
                "calc": "Calculator.exe",
                "powerpoint": "POWERPNT.EXE",
                "ppt": "POWERPNT.EXE",
                "word": "WINWORD.EXE",
                "excel": "EXCEL.EXE",
            }
            
            # Method 1: By window title
            if window_title:
                try:
                    app = Application(backend="uia").connect(title=window_title, timeout=3)
                    self._app_connections[cache_key] = app
                    return app
                except:
                    pass
            
            # Method 2: By process name
            try:
                process_name = process_map.get(app_name.lower(), app_name)
                app = Application(backend="uia").connect(path=process_name, timeout=3)
                self._app_connections[cache_key] = app
                return app
            except:
                pass
            
            # Method 3: By title pattern
            try:
                app = Application(backend="uia").connect(title_re=fr".*{app_name}.*", timeout=3)
                self._app_connections[cache_key] = app
                return app
            except:
                pass
            
            logger.warning(f"Could not connect to app: {app_name}")
            return None
                    
        except Exception as e:
            logger.error(f"Error getting app connection: {e}")
            return None
    
    def _get_automation_id(self, elem) -> Optional[str]:
        """Extract automation_id - tries multiple methods, returns None if truly empty"""
        try:
            elem_info = elem.element_info
            
            # Method 1: Direct access
            if hasattr(elem_info, 'automation_id'):
                try:
                    aid = elem_info.automation_id
                    if aid and aid.strip():
                        return aid
                except:
                    pass
            
            # Method 2: Via wrapper
            try:
                wrapped = elem.wrapper_object()
                if hasattr(wrapped.element_info, 'automation_id'):
                    aid = wrapped.element_info.automation_id
                    if aid and aid.strip():
                        return aid
            except:
                pass
            
            # Method 3: Via UIA element properties
            try:
                uia_elem = elem_info.element
                if hasattr(uia_elem, 'CurrentAutomationId'):
                    aid = uia_elem.CurrentAutomationId
                    if aid and aid.strip():
                        return aid
            except:
                pass
            
            # Method 4: Try GetCurrentPropertyValue with UIA property ID
            try:
                from comtypes.gen.UIAutomationClient import UIA_AutomationIdPropertyId
                uia_elem = elem_info.element
                if hasattr(uia_elem, 'GetCurrentPropertyValue'):
                    aid = uia_elem.GetCurrentPropertyValue(UIA_AutomationIdPropertyId)
                    if aid and aid.strip():
                        return aid
            except:
                pass
            
        except:
            pass
        
        return None
    
    def _deep_element_search(self, element, max_depth: int = 3, current_depth: int = 0) -> List:
        """Recursively search for elements with depth limit"""
        if current_depth >= max_depth:
            return []
        
        results = []
        try:
            children = element.children()
            results.extend(children)
            
            for child in children[:20]:  # Limit breadth too
                try:
                    nested = self._deep_element_search(child, max_depth, current_depth + 1)
                    results.extend(nested)
                except:
                    continue
        except:
            pass
        
        return results
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute UI automation action"""
        if not self._ensure_windows():
            return ToolResult(
                success=False,
                output=None,
                error="UI Automation is only available on Windows"
            )
        
        try:
            if action == "get_elements":
                return await self.get_elements(**kwargs)
            elif action == "find_element":
                return await self.find_element_universal(**kwargs)
            elif action == "click_element":
                return await self.click_element_universal(**kwargs)
            elif action == "type_text":
                return await self.type_text_universal(**kwargs)
            elif action == "get_text":
                return await self.get_text(**kwargs)
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"UI Automation error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    async def get_elements(self, app_name: str, window_title: Optional[str] = None,
                        control_type: Optional[str] = None, visible_only: bool = True,
                        depth: str = "normal") -> ToolResult:
        """
        Universal element discovery
        Only includes automation_id if it's actually present (not empty)
        """
        try:
            app = await self._get_app_connection(app_name, window_title)
            if not app:
                app = await self._get_app_connection(app_name, window_title, force_reconnect=True)
                if not app:
                    return ToolResult(success=False, output=None, 
                                    error=f"Could not connect to: {app_name}")
            
            window = app.top_window()
            await asyncio.sleep(0.3)
            
            # Get elements with timeout protection
            all_elements = []
            
            try:
                if depth == "shallow":
                    all_elements = window.children()
                elif depth == "deep":
                    # Reduced max_depth from 5 to 3 for speed
                    all_elements = self._deep_element_search(window, max_depth=3)
                else:  # normal
                    # Wrap descendants() with timeout
                    async def get_descendants():
                        return list(window.descendants())
                    
                    try:
                        all_elements = await asyncio.wait_for(
                            asyncio.to_thread(lambda: list(window.descendants())),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("descendants() timed out, using shallow search")
                        all_elements = window.children()
                        
            except Exception as e:
                logger.warning(f"Error getting elements: {e}, falling back to children()")
                all_elements = window.children()
            
            logger.info(f"Found {len(all_elements)} total elements")
            
            # Prioritize elements
            HIGH_PRIORITY = ["Button", "MenuItem", "ListItem", "TabItem", "CheckBox", "RadioButton"]
            MEDIUM_PRIORITY = ["Edit", "ComboBox", "List", "Tree", "Table", "Image", "Hyperlink"]
            LOW_PRIORITY = ["Text", "Static", "Group", "Pane"]
            
            elements_by_priority = {"high": [], "medium": [], "low": []}
            
            for elem in all_elements[:200]:  # Limit to first 200 for performance
                try:
                    if visible_only:
                        try:
                            if not elem.is_visible():
                                continue
                        except:
                            continue
                    
                    elem_info = elem.element_info
                    ctrl_type = str(elem_info.control_type) if hasattr(elem_info, 'control_type') else None
                    name = elem_info.name if hasattr(elem_info, 'name') else ""
                    auto_id = self._get_automation_id(elem)
                    
                    if not (name or auto_id or ctrl_type in HIGH_PRIORITY):
                        continue
                    
                    element_data = {
                        "name": name,
                        "control_type": ctrl_type or "",
                        "class_name": elem_info.class_name if hasattr(elem_info, 'class_name') else "",
                    }
                    
                    # ONLY add automation_id if it's actually present
                    if auto_id:
                        element_data["automation_id"] = auto_id
                    
                    try:
                        rect = elem.rectangle()
                        element_data["bounds"] = {
                            "x": rect.left, "y": rect.top,
                            "w": rect.width(), "h": rect.height()
                        }
                    except:
                        pass
                    
                    # Categorize
                    if ctrl_type in HIGH_PRIORITY:
                        elements_by_priority["high"].append(element_data)
                    elif ctrl_type in MEDIUM_PRIORITY:
                        elements_by_priority["medium"].append(element_data)
                    elif ctrl_type in LOW_PRIORITY:
                        elements_by_priority["low"].append(element_data)
                        
                except Exception as e:
                    logger.debug(f"Error processing element: {e}")
                    continue
            
            total = sum(len(v) for v in elements_by_priority.values())
            
            # Build summary
            type_counts = {}
            for priority_list in elements_by_priority.values():
                for elem in priority_list:
                    ct = elem["control_type"]
                    type_counts[ct] = type_counts.get(ct, 0) + 1
            
            summary = f"Found {total} interactive elements. "
            summary += f"Types: {', '.join([f'{k}({v})' for k, v in sorted(type_counts.items(), key=lambda x: -x[1])[:8]])}. "
            
            # Select elements
            selected = []
            selected.extend(elements_by_priority["high"][:30])
            selected.extend(elements_by_priority["medium"][:20])
            selected.extend(elements_by_priority["low"][:10])
            
            named = [e["name"] for e in selected if e["name"]][:15]
            if named:
                summary += f"Named: {', '.join(named)}"
            
            output = {
                "summary": summary,
                "elements": selected,
                "by_priority": {
                    "high": elements_by_priority["high"][:20],
                    "medium": elements_by_priority["medium"][:15],
                },
                "total_count": total
            }
            
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            logger.error(f"Error in get_elements: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    async def click_element_universal(self, app_name: str,
                                    name: Optional[str] = None,
                                    automation_id: Optional[str] = None,
                                    control_type: Optional[str] = None,
                                    text_contains: Optional[str] = None,
                                    window_title: Optional[str] = None) -> ToolResult:
        """Universal click - prioritizes name when automation_id is blank or None"""
        try:
            app = await self._get_app_connection(app_name, window_title)
            if not app:
                return ToolResult(success=False, output=None, 
                                error=f"Could not connect to: {app_name}")
            
            window = app.top_window()
            
            # Normalize inputs
            if text_contains and not name:
                name = text_contains
            
            # Clean automation_id - treat empty string as None
            if automation_id and not automation_id.strip():
                automation_id = None
            
            last_error = None
            
            # METHOD 1: Try automation_id if provided and not empty
            if automation_id:
                try:
                    elem = window.child_window(automation_id=automation_id).wrapper_object()
                    if elem.exists() and elem.is_visible():
                        elem.click_input()
                        logger.info(f"Clicked by automation_id: {automation_id}")
                        return ToolResult(success=True, output=f"Clicked: {name or automation_id}")
                except Exception as e:
                    logger.debug(f"Click by automation_id failed: {e}")
                    last_error = str(e)
            
            # METHOD 2: Try exact name match
            if name:
                try:
                    elem = window.child_window(name=name).wrapper_object()
                    if elem.exists() and elem.is_visible():
                        elem.click_input()
                        logger.info(f"Clicked by exact name: {name}")
                        return ToolResult(success=True, output=f"Clicked: {name}")
                except Exception as e:
                    logger.debug(f"Click by exact name failed: {e}")
                    last_error = str(e)
            
            # METHOD 3: Try partial name match
            if name:
                try:
                    escaped_name = re.escape(name)
                    elem = window.child_window(name_re=f".*{escaped_name}.*").wrapper_object()
                    if elem.exists() and elem.is_visible():
                        elem.click_input()
                        logger.info(f"Clicked by partial name: {name}")
                        return ToolResult(success=True, output=f"Clicked: {name}")
                except Exception as e:
                    logger.debug(f"Click by partial name failed: {e}")
                    last_error = str(e)
            
            # METHOD 4: Try by control_type
            if control_type:
                try:
                    all_elements = window.descendants()
                    for elem in all_elements[:50]:
                        try:
                            elem_info = elem.element_info
                            elem_type = str(elem_info.control_type) if hasattr(elem_info, 'control_type') else None
                            elem_name = elem_info.name if hasattr(elem_info, 'name') else ""
                            
                            if elem_type == control_type:
                                if name:
                                    if name.lower() in elem_name.lower():
                                        if elem.exists() and elem.is_visible():
                                            elem.click_input()
                                            logger.info(f"Clicked by control_type + name: {elem_name}")
                                            return ToolResult(success=True, output=f"Clicked: {elem_name}")
                                else:
                                    if elem.exists() and elem.is_visible():
                                        elem.click_input()
                                        logger.info(f"Clicked first {control_type}")
                                        return ToolResult(success=True, output=f"Clicked {control_type}")
                        except:
                            continue
                except Exception as e:
                    logger.debug(f"Click by control_type failed: {e}")
                    last_error = str(e)
            
            # METHOD 5: Coordinate-based fallback (find element and click its center)
            if name or automation_id:
                try:
                    search_criteria = {}
                    if automation_id:
                        search_criteria["automation_id"] = automation_id
                    elif name:
                        search_criteria["name"] = name
                    
                    elem = window.child_window(**search_criteria).wrapper_object()
                    if elem.exists():
                        rect = elem.rectangle()
                        center_x = rect.left + rect.width() // 2
                        center_y = rect.top + rect.height() // 2
                        
                        # Use pyautogui for coordinate click
                        import pyautogui
                        pyautogui.click(center_x, center_y)
                        logger.info(f"Clicked by coordinates: ({center_x}, {center_y})")
                        return ToolResult(success=True, output=f"Clicked: {name or automation_id}")
                except Exception as e:
                    logger.debug(f"Coordinate click failed: {e}")
                    last_error = str(e)
            
            # All methods failed
            error_msg = f"Could not click element"
            if name:
                error_msg += f" '{name}'"
            if control_type:
                error_msg += f" ({control_type})"
            if last_error:
                error_msg += f". Last error: {last_error[:100]}"
            
            return ToolResult(success=False, output=None, error=error_msg)
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Click failed: {str(e)}")
    
    async def type_text_universal(self, app_name: str, text: str,
                                  target_name: Optional[str] = None,
                                  target_automation_id: Optional[str] = None,
                                  window_title: Optional[str] = None,
                                  clear_first: bool = True) -> ToolResult:
        """Universal text typing"""
        try:
            app = await self._get_app_connection(app_name, window_title)
            if not app:
                return ToolResult(success=False, output=None, error=f"Could not connect to: {app_name}")
            
            window = app.top_window()
            
            # Clean automation_id
            if target_automation_id and not target_automation_id.strip():
                target_automation_id = None
            
            # Type into specified element or focused element
            if target_automation_id or target_name:
                elem = (window.child_window(automation_id=target_automation_id) if target_automation_id
                       else window.child_window(name=target_name))
                
                if clear_first:
                    elem.set_focus()
                    elem.type_keys("^a{BACKSPACE}")
                
                elem.type_keys(text, with_spaces=True)
                return ToolResult(success=True, output=f"Typed {len(text)} characters")
            
            # Find focused or first Edit control
            try:
                focused = window.get_focus()
                if focused:
                    if clear_first:
                        focused.type_keys("^a{BACKSPACE}")
                    focused.type_keys(text, with_spaces=True)
                    return ToolResult(success=True, output=f"Typed into focused element")
            except:
                pass
            
            # Find first Edit control
            edit_controls = window.descendants(control_type="Edit")
            for edit in edit_controls:
                if edit.is_visible() and edit.is_enabled():
                    edit.set_focus()
                    if clear_first:
                        edit.type_keys("^a{BACKSPACE}")
                    edit.type_keys(text, with_spaces=True)
                    return ToolResult(success=True, output=f"Typed into Edit control")
            
            return ToolResult(success=False, output=None, error="No input element found")
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    async def get_text(self, app_name: str, window_title: Optional[str] = None,
                      name: Optional[str] = None, automation_id: Optional[str] = None) -> ToolResult:
        """Get text from element"""
        try:
            app = await self._get_app_connection(app_name, window_title)
            if not app:
                return ToolResult(success=False, output=None, error=f"Could not connect to: {app_name}")
            
            window = app.top_window()
            
            # Clean automation_id
            if automation_id and not automation_id.strip():
                automation_id = None
            
            if automation_id:
                elem = window.child_window(automation_id=automation_id)
            elif name:
                elem = window.child_window(name=name)
            else:
                return ToolResult(success=False, output=None, error="Need name or automation_id")
            
            text = elem.window_text()
            return ToolResult(success=True, output=text)
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    def validate_params(self, **kwargs) -> bool:
        """Validate parameters"""
        return "app_name" in kwargs
