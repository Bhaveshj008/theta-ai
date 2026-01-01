"""
Screen Capture and Visual Perception
"""
import warnings
import os
import sys
# Suppress PyTorch warnings about pin_memory - do this BEFORE any torch imports
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')
# Specifically suppress torch warnings
warnings.filterwarnings('ignore', message='.*pin_memory.*')
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', module='torch')
warnings.filterwarnings('ignore', module='torch.utils.data')
warnings.filterwarnings('ignore', module='torch.utils.data.dataloader')

import PIL.Image
# Monkey patch for Pillow 10.0.0+ compatibility (Fixes EasyOCR crash)
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import io
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from PIL import Image, ImageDraw
import numpy as np
import cv2
import mss
import pyautogui
import easyocr
import pytesseract
import logging

from agent.config import settings

logger = logging.getLogger(__name__)

# Also suppress at logging level for torch - do this early
import logging as py_logging
py_logging.getLogger("torch.utils.data.dataloader").setLevel(py_logging.CRITICAL)
py_logging.getLogger("torch").setLevel(py_logging.ERROR)
py_logging.getLogger("easyocr").setLevel(py_logging.ERROR)


@dataclass
class BoundingBox:
    """Represents a rectangular region"""
    x: int
    y: int
    width: int
    height: int
    
    def to_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)
    
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class UIElement:
    """Detected UI element"""
    text: str
    bbox: BoundingBox
    confidence: float
    element_type: str = "text"  # text, button, input, link, image
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "bbox": self.bbox.to_tuple(),
            "confidence": self.confidence,
            "type": self.element_type,
        }


@dataclass
class ScreenState:
    """Complete snapshot of screen state"""
    screenshot: Image.Image
    elements: List[UIElement] = field(default_factory=list)
    raw_text: str = ""
    active_window_title: str = ""
    mouse_position: Tuple[int, int] = (0, 0)
    screen_size: Tuple[int, int] = (0, 0)
    timestamp: float = field(default_factory=time.time)
    
    def to_bytes(self, format: str = "PNG") -> bytes:
        """Convert screenshot to bytes"""
        buffer = io.BytesIO()
        self.screenshot.save(buffer, format=format)
        return buffer.getvalue()
    
    def find_element(self, text: str, case_sensitive: bool = False) -> Optional[UIElement]:
        """Find element by text"""
        search_text = text if case_sensitive else text.lower()
        for elem in self.elements:
            elem_text = elem.text if case_sensitive else elem.text.lower()
            if search_text in elem_text:
                return elem
        return None
    
    def get_summary(self) -> str:
        """Get text summary of screen state"""
        summary = f"Screen: {self.screen_size[0]}x{self.screen_size[1]}\n"
        summary += f"Active Window: {self.active_window_title}\n"
        summary += f"Elements Found: {len(self.elements)}\n"
        summary += f"Mouse Position: {self.mouse_position}\n\n"
        summary += f"Extracted Text:\n{self.raw_text[:500]}..."
        return summary


class ScreenCapture:
    """Handles screen capture and basic analysis"""
    
    def __init__(self):
        self.sct = mss.mss()
        self.last_screenshot: Optional[Image.Image] = None
        self.last_capture_time: float = 0
    
    def capture(self, region: Optional[Dict[str, int]] = None) -> Image.Image:
        """
        Capture screenshot
        
        Args:
            region: {"top": y, "left": x, "width": w, "height": h}
        
        Returns:
            PIL Image
        """
        if region:
            sct_img = self.sct.grab(region)
        else:
            # Capture primary monitor
            monitor = self.sct.monitors[1]
            sct_img = self.sct.grab(monitor)
        
        # Convert to PIL Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        self.last_screenshot = img
        self.last_capture_time = time.time()
        
        return img
    
    def capture_active_window(self) -> Optional[Image.Image]:
        """Capture only the active window"""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                region = {
                    "left": active.left,
                    "top": active.top,
                    "width": active.width,
                    "height": active.height,
                }
                return self.capture(region)
        except Exception as e:
            logger.warning(f"Could not capture active window: {e}")
        
        return self.capture()
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen dimensions"""
        monitor = self.sct.monitors[1]
        return (monitor["width"], monitor["height"])
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        return pyautogui.position()
    
    def get_active_window_title(self) -> str:
        """Get active window title"""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            return active.title if active else "Unknown"
        except Exception:
            return "Unknown"


class OCREngine:
    """Text extraction using EasyOCR and Tesseract"""
    
    def __init__(self):
        logger.info("Initializing OCR engine...")
        
        # Suppress all warnings during EasyOCR initialization and usage
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Also suppress torch warnings
            warnings.filterwarnings('ignore', category=UserWarning, module='torch')
            warnings.filterwarnings('ignore', message='.*pin_memory.*')
            
            self.easy_ocr = easyocr.Reader(
                settings.OCR_LANGUAGES,
                gpu=settings.USE_GPU_OCR,
                verbose=False
            )
        logger.info("OCR engine ready")
    
    def extract_text(self, image: Image.Image, detailed: bool = True) -> Tuple[str, List[UIElement]]:
        """
        Extract text from image
        
        Args:
            image: PIL Image
            detailed: Return detailed element info
        
        Returns:
            (raw_text, elements)
        """
        # Convert PIL to numpy
        img_array = np.array(image)
        
        # Use EasyOCR for better accuracy
        try:
            # Aggressively suppress warnings during OCR - redirect stderr temporarily
            import warnings
            import io
            import contextlib
            
            # Capture and suppress stderr (where torch warnings go)
            stderr_capture = io.StringIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                warnings.filterwarnings('ignore')
                with contextlib.redirect_stderr(stderr_capture):
                    try:
                        results = self.easy_ocr.readtext(img_array)
                    except Exception:
                        # If redirect fails, try without it
                        results = self.easy_ocr.readtext(img_array)
            
            elements = []
            text_parts = []
            
            for (bbox, text, confidence) in results:
                # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]
                
                x = int(min(x_coords))
                y = int(min(y_coords))
                width = int(max(x_coords) - x)
                height = int(max(y_coords) - y)
                
                element = UIElement(
                    text=text,
                    bbox=BoundingBox(x, y, width, height),
                    confidence=confidence,
                    element_type="text"
                )
                elements.append(element)
                text_parts.append(text)
            
            raw_text = "\n".join(text_parts)
            logger.debug(f"OCR extracted {len(elements)} text elements")
            
            return raw_text, elements
            
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}, falling back to Tesseract")
            # Fallback to Tesseract
            raw_text = pytesseract.image_to_string(image)
            return raw_text, []
    
    def find_text_location(self, image: Image.Image, search_text: str) -> Optional[BoundingBox]:
        """Find location of specific text on screen"""
        _, elements = self.extract_text(image)
        search_lower = search_text.lower()
        
        for elem in elements:
            if search_lower in elem.text.lower():
                return elem.bbox
        
        return None


class PerceptionEngine:
    """Main perception engine combining all vision capabilities"""
    
    def __init__(self):
        self.capture = ScreenCapture()
        self.ocr = OCREngine()
    
    def perceive(self, capture_region: Optional[Dict] = None) -> ScreenState:
        """
        Capture and analyze current screen state
        
        Args:
            capture_region: Optional region to capture
        
        Returns:
            ScreenState object
        """
        logger.debug("Perceiving screen state...")
        
        # Capture screenshot
        screenshot = self.capture.capture(capture_region)
        
        # Extract text and elements
        raw_text, elements = self.ocr.extract_text(screenshot)
        
        # Get system info
        mouse_pos = self.capture.get_mouse_position()
        screen_size = self.capture.get_screen_size()
        window_title = self.capture.get_active_window_title()
        
        state = ScreenState(
            screenshot=screenshot,
            elements=elements,
            raw_text=raw_text,
            active_window_title=window_title,
            mouse_position=mouse_pos,
            screen_size=screen_size,
            timestamp=time.time()
        )
        
        logger.info(f"Perceived state: {len(elements)} elements, window='{window_title}'")
        return state
    
    def perceive_active_window(self) -> ScreenState:
        """Perceive only the active window"""
        screenshot = self.capture.capture_active_window()
        raw_text, elements = self.ocr.extract_text(screenshot)
        
        return ScreenState(
            screenshot=screenshot,
            elements=elements,
            raw_text=raw_text,
            active_window_title=self.capture.get_active_window_title(),
            mouse_position=self.capture.get_mouse_position(),
            screen_size=self.capture.get_screen_size(),
        )
    
    def find_and_click(self, text: str) -> bool:
        """Find text on screen and click it"""
        state = self.perceive()
        element = state.find_element(text)
        
        if element:
            center = element.bbox.center()
            pyautogui.click(center[0], center[1])
            logger.info(f"Clicked on '{text}' at {center}")
            return True
        
        logger.warning(f"Could not find '{text}' on screen")
        return False
    
    def wait_for_text(self, text: str, timeout: float = 10.0, interval: float = 0.5) -> bool:
        """Wait for text to appear on screen"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            state = self.perceive()
            if state.find_element(text):
                logger.info(f"Found '{text}' on screen")
                return True
            time.sleep(interval)
        
        logger.warning(f"Timeout waiting for '{text}'")
        return False