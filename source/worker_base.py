"""
Worker Base - Shared base class và imports cho tất cả worker threads
"""

import sys
import os
import re
import time
import glob
import shutil
import tempfile
import traceback
import random

from PyQt6.QtCore import QThread, pyqtSignal

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.firefox.service import Service
    from selenium.webdriver.firefox.options import Options
    from webdriver_manager.firefox import GeckoDriverManager
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)


class WorkerThread(QThread):
    """Base worker thread với output signal"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self):
        super().__init__()
        self._stop_requested = False
        self.driver = None
    
    def log(self, message):
        """Emit log message to GUI"""
        self.output_signal.emit(str(message))
    
    def stop(self):
        """Request stop"""
        self._stop_requested = True
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def _interruptible_wait(self, condition_func, timeout_seconds, check_interval=1):
        """Wait với khả năng interrupt bởi stop request.
        
        Args:
            condition_func: Hàm trả về True khi điều kiện thỏa mãn
            timeout_seconds: Tổng thời gian chờ tối đa
            check_interval: Khoảng thời gian giữa các lần check (giây)
            
        Returns:
            (success, was_stopped) - success=True nếu condition thỏa mãn, was_stopped=True nếu bị stop
        """
        elapsed = 0
        while elapsed < timeout_seconds:
            if self._stop_requested:
                return False, True  # Bị stop
            
            try:
                if condition_func():
                    return True, False  # Thành công
            except:
                pass
            
            # Sleep theo từng bước nhỏ để có thể check stop thường xuyên
            sleep_time = min(check_interval, timeout_seconds - elapsed)
            for _ in range(int(sleep_time * 2)):  # Check mỗi 0.5s
                if self._stop_requested:
                    return False, True
                time.sleep(0.5)
            
            elapsed += sleep_time
        
        return False, False  # Timeout
    
    def _verify_and_ensure_send_clicked(self, max_retries=3):
        """Verify send button was clicked (changed to stop button).
        If not clicked, retry clicking.
        
        Returns:
            True - Send button đã được click (button đã chuyển sang stop)
            False - Không thể click send button
        """
        for retry in range(max_retries):
            try:
                # Check if button has "stop" class
                send_button = self.driver.find_element(By.CSS_SELECTOR, "button.send-button")
                button_class = send_button.get_attribute("class")
                
                if "stop" in button_class:
                    if retry == 0:
                        self.log("-> ✓ Send button đã được click (button = stop)")
                    else:
                        self.log(f"-> ✓ Send button đã được click sau {retry + 1} lần thử")
                    return True
                
                # Button vẫn là submit, chưa click thành công
                if retry == 0:
                    self.log("-> ⚠️ Send button chưa được click, thử click lại...")
                else:
                    self.log(f"-> ⚠️ Lần {retry + 1}: Send button vẫn chưa click, thử lại...")
                
                # Try clicking again
                try:
                    # Click bằng JS
                    self.driver.execute_script("arguments[0].click();", send_button)
                    time.sleep(2)
                except:
                    # Fallback: click bằng selenium
                    send_button.click()
                    time.sleep(2)
                
            except Exception as e:
                self.log(f"-> ⚠️ Không tìm thấy send button: {str(e)[:50]}")
                time.sleep(1)
        
        self.log("-> ❌ Không thể click send button sau nhiều lần thử")
        return False
    
    def _send_prompt_and_verify(self, input_box, prompt_text):
        """Gửi prompt và verify button đã click thành công
        
        Args:
            input_box: Element input box của Gemini
            prompt_text: Text prompt cần gửi
        
        Returns:
            True - Prompt đã được gửi thành công
            False - Không thể gửi prompt (cần restart browser)
        """
        try:
            # Gõ từng ký tự như người thật (tránh bị detect automation)
            self.log(f"-> Đang gõ prompt ({len(prompt_text)} ký tự)...")
            for i, char in enumerate(prompt_text):
                if self._stop_requested:
                    return False
                input_box.send_keys(char)
                # Random delay giữa các ký tự (0.01-0.03s)
                time.sleep(random.uniform(0.01, 0.03))
                # Log progress mỗi 500 ký tự
                if (i + 1) % 500 == 0:
                    self.log(f"   ... đã gõ {i + 1}/{len(prompt_text)} ký tự")
            self.log(f"-> ✓ Đã gõ xong {len(prompt_text)} ký tự")
            time.sleep(1)
            
            # Click Send button
            self.log("-> Đang tìm nút Send...")
            try:
                send_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "mat-icon[fonticon='send']"))
                )
                send_button.click()
                self.log("-> ✓ Đã click nút Send")
                time.sleep(2)
            except Exception as e:
                self.log(f"!!! Không tìm thấy nút Send, thử dùng Enter: {str(e)[:50]}")
                input_box.send_keys(Keys.ENTER)
                time.sleep(2)
            
            # Verify send button đã được click (chuyển thành stop button)
            self.log("-> Đang verify send button...")
            if not self._verify_and_ensure_send_clicked():
                self.log("❌ Không thể gửi prompt sau nhiều lần thử")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"!!! Lỗi khi gửi prompt: {str(e)[:100]}")
            return False
    
    def toggle_firefox_visibility(self, show):
        """Toggle Firefox window visibility in real-time
        
        Args:
            show: True để hiện window, False để ẩn
        """
        if not self.driver:
            return
        
        # Nếu đang ở headless mode, không làm gì
        if hasattr(self, 'headless') and self.headless:
            return
        
        try:
            if show:
                # Hiển thị Firefox window - đưa ra foreground
                self.driver.set_window_size(1200, 800)
                time.sleep(0.2)  # Đợi window resize
                self.driver.set_window_position(100, 100)
                time.sleep(0.2)  # Đợi window move
                
                # Focus vào window
                try:
                    self.driver.switch_to.window(self.driver.current_window_handle)
                    self.driver.execute_script("window.focus();")
                    
                    # Windows-specific: đưa window ra foreground
                    import ctypes
                    try:
                        # Search for Firefox window using nonlocal list
                        found_windows = []
                        
                        def callback(hwnd, lparam):
                            if ctypes.windll.user32.IsWindowVisible(hwnd):
                                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                                if length > 0:
                                    buffer = ctypes.create_unicode_buffer(length + 1)
                                    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                                    if "Mozilla Firefox" in buffer.value or "Gemini" in buffer.value:
                                        found_windows.append(hwnd)
                            return True
                        
                        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_long, ctypes.c_long)
                        ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
                        
                        if found_windows:
                            # Set foreground window
                            ctypes.windll.user32.SetForegroundWindow(found_windows[0])
                            ctypes.windll.user32.ShowWindow(found_windows[0], 9)  # SW_RESTORE
                    except:
                        pass  # Fallback nếu ctypes không hoạt động
                except:
                    pass
            else:
                # Ẩn Firefox window - move ra ngoài màn hình
                self.driver.set_window_position(-10000, -10000)
                time.sleep(0.1)
                
        except Exception as e:
            pass  # Ignore errors if browser is closing or not available
    
    def _ensure_pro_mode(self):
        """Kiểm tra và chọn mode theo setting (Pro hoặc Thinking)
        
        Returns:
            True - Mode đã được chọn thành công
            False - Không thể chọn mode
            'LIMITED' - Mode đang bị giới hạn và không có fallback
        """
        if not self.driver:
            self.log("!!! Driver chưa được khởi tạo")
            return False
        
        # Xác định mode muốn sử dụng
        target_mode = getattr(self, 'gemini_mode', 'Pro')
        use_thinking = "thinking" in target_mode.lower() or "tư duy" in target_mode.lower()
        
        try:
            # Tìm label hiện tại trong logo-pill-label-container
            mode_label = self.driver.find_element(
                By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container'] span"
            )
            current_mode = mode_label.text.strip()
            
            # Kiểm tra xem đã đúng mode chưa
            if use_thinking:
                if current_mode in ["Thinking", "Tư duy"]:
                    self.log(f"-> Đang ở {current_mode} mode")
                    return True
            else:
                if current_mode == "Pro":
                    self.log("-> Đang ở Pro mode")
                    return True
            
            self.log(f"-> Đang ở mode '{current_mode}', chuyển sang {target_mode}...")
            
            # Click vào container để mở dropdown (dùng JS click để tránh bị chặn)
            mode_container = self.driver.find_element(
                By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']"
            )
            self.driver.execute_script("arguments[0].click();", mode_container)
            time.sleep(1)
            
            # Chọn mode theo setting
            if use_thinking:
                # User muốn dùng Thinking mode
                result = self._switch_to_thinking_mode(dropdown_already_open=True)
                if result:
                    return True
                self.log("!!! Không thể chọn Thinking mode, thử fallback sang Pro...")
                # Fallback sang Pro nếu Thinking không có (dropdown vẫn mở)
                return self._switch_to_pro_mode()
            else:
                # User muốn dùng Pro mode
                result = self._switch_to_pro_mode()
                if result == 'LIMITED':
                    # Pro bị limit, thử fallback sang Thinking (dropdown vẫn mở)
                    self.log("⚠️ Pro mode bị giới hạn, thử chuyển sang Thinking mode...")
                    thinking_result = self._switch_to_thinking_mode(dropdown_already_open=True)
                    if thinking_result:
                        return True
                    return 'LIMITED'
                return result
            
        except Exception as e:
            self.log(f"!!! Lỗi khi kiểm tra/chọn mode: {str(e)[:100]}")
            return False
    
    
    def _switch_to_thinking_mode(self, dropdown_already_open=False):
        """Chuyển sang Thinking/Tư duy mode
        
        Args:
            dropdown_already_open: True nếu dropdown đã mở rồi (không cần click lại)
        
        Returns:
            True - Đã chọn Thinking mode thành công
            False - Không thể chọn Thinking mode
        """
        try:
            # Mở dropdown nếu chưa mở
            if not dropdown_already_open:
                try:
                    mode_container = self.driver.find_element(
                        By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']"
                    )
                    self.driver.execute_script("arguments[0].click();", mode_container)
                    time.sleep(1)
                except:
                    pass
            
            # Phương pháp 1: Tìm theo text trong span.mode-title (ĐÁNG TIN CẬY NHẤT)
            try:
                mode_titles = self.driver.find_elements(By.CSS_SELECTOR, "span.mode-title")
                self.log(f"-> Tìm thấy {len(mode_titles)} modes available")
                for title in mode_titles:
                    text = title.text.strip()
                    self.log(f"   Mode: '{text}'")
                    if text in ["Thinking", "Tư duy"]:
                        # Kiểm tra parent button có disabled không
                        try:
                            parent_button = title.find_element(By.XPATH, "./ancestor::button[1]")
                            is_disabled = parent_button.get_attribute("disabled") or parent_button.get_attribute("aria-disabled") == "true"
                            if not is_disabled:
                                self.driver.execute_script("arguments[0].click();", title)
                                self.log(f"✅ Đã chuyển sang {text} mode")
                                time.sleep(1)
                                return True
                            else:
                                self.log(f"   -> {text} mode bị disabled")
                        except Exception as e:
                            self.log(f"   -> Lỗi khi check {text}: {str(e)[:50]}")
            except Exception as e:
                self.log(f"!!! Lỗi khi tìm mode-title: {str(e)[:100]}")
            
            # Phương pháp 2: Thử tìm bằng partial match trong data-test-id
            try:
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test-id^='bard-mode-option-']")
                self.log(f"-> Tìm thấy {len(all_buttons)} mode buttons với data-test-id")
                for button in all_buttons:
                    test_id = button.get_attribute("data-test-id") or ""
                    self.log(f"   Button: {test_id}")
                    if "thinking" in test_id.lower() or "duy" in test_id.lower():
                        is_disabled = button.get_attribute("disabled") or button.get_attribute("aria-disabled") == "true"
                        if not is_disabled:
                            self.driver.execute_script("arguments[0].click();", button)
                            self.log(f"✅ Đã chuyển sang Thinking mode (by test-id: {test_id})")
                            time.sleep(1)
                            return True
                        else:
                            self.log(f"   -> Button bị disabled")
            except Exception as e:
                self.log(f"!!! Lỗi khi tìm buttons: {str(e)[:100]}")
            
            self.log("!!! Không tìm thấy Thinking/Tư duy mode hoặc mode đã bị giới hạn")
            return False
            
        except Exception as e:
            self.log(f"!!! Lỗi khi chuyển sang Thinking mode: {str(e)[:100]}")
            return False
    
    def _switch_to_pro_mode(self):
        """Chuyển sang Pro mode
        
        Returns:
            True - Đã chọn Pro mode thành công
            False - Không tìm thấy Pro mode
            'LIMITED' - Pro mode bị giới hạn
        """
        try:
            # Kiểm tra xem Pro mode có bị disabled không
            try:
                pro_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-test-id='bard-mode-option-pro']")
                
                # Check if disabled
                is_disabled = pro_button.get_attribute("disabled") or pro_button.get_attribute("aria-disabled") == "true"
                
                if is_disabled:
                    # Check for limit message
                    button_html = pro_button.get_attribute("outerHTML")
                    if "Limit resets" in button_html or "mode-desc" in button_html:
                        try:
                            desc_span = pro_button.find_element(By.CSS_SELECTOR, "span.mode-desc")
                            limit_msg = desc_span.text
                            self.log(f"⚠️ Pro mode bị giới hạn: {limit_msg}")
                        except:
                            self.log(f"⚠️ Pro mode bị giới hạn (disabled)")
                        return 'LIMITED'
            except:
                pass  # Không tìm thấy button, tiếp tục logic cũ
            
            # Tìm và click vào Pro option trong dropdown
            pro_options = self.driver.find_elements(By.CSS_SELECTOR, "span.mode-title")
            for option in pro_options:
                if "Pro" in option.text:
                    self.driver.execute_script("arguments[0].click();", option)
                    self.log("-> Đã chọn Pro mode")
                    time.sleep(1)
                    return True
            
            # Fallback: thử tìm bằng text
            try:
                pro_option = self.driver.find_element(By.XPATH, "//span[contains(@class, 'mode-title') and contains(text(), 'Pro')]")
                self.driver.execute_script("arguments[0].click();", pro_option)
                self.log("-> Đã chọn Pro mode (fallback)")
                time.sleep(1)
                return True
            except:
                pass
            
            self.log("!!! Không tìm thấy Pro option")
            return False
            
        except Exception as e:
            self.log(f"!!! Lỗi khi chọn Pro mode: {str(e)[:100]}")
            return False
    
    def _switch_to_thinking_mode(self, dropdown_already_open=False):
        """Chuyển sang Thinking/Tư duy mode
        
        Args:
            dropdown_already_open: True nếu dropdown đã mở rồi (không cần click lại)
        
        Returns:
            True - Đã chọn Thinking mode thành công
            False - Không thể chọn Thinking mode
        """
        try:
            # Mở dropdown nếu chưa mở
            if not dropdown_already_open:
                try:
                    mode_container = self.driver.find_element(
                        By.CSS_SELECTOR, "div[data-test-id='logo-pill-label-container']"
                    )
                    self.driver.execute_script("arguments[0].click();", mode_container)
                    time.sleep(1)
                except:
                    pass
            
            # Phương pháp 1: Tìm theo text trong span.mode-title (ĐÁNG TIN CẬY NHẤT)
            try:
                mode_titles = self.driver.find_elements(By.CSS_SELECTOR, "span.mode-title")
                self.log(f"-> Tìm thấy {len(mode_titles)} modes available")
                for title in mode_titles:
                    text = title.text.strip()
                    self.log(f"   Mode: '{text}'")
                    if text in ["Thinking", "Tư duy"]:
                        # Kiểm tra parent button có disabled không
                        try:
                            parent_button = title.find_element(By.XPATH, "./ancestor::button[1]")
                            is_disabled = parent_button.get_attribute("disabled") or parent_button.get_attribute("aria-disabled") == "true"
                            if not is_disabled:
                                self.driver.execute_script("arguments[0].click();", title)
                                self.log(f"✅ Đã chuyển sang {text} mode")
                                time.sleep(1)
                                return True
                            else:
                                self.log(f"   -> {text} mode bị disabled")
                        except Exception as e:
                            self.log(f"   -> Lỗi khi check {text}: {str(e)[:50]}")
            except Exception as e:
                self.log(f"!!! Lỗi khi tìm mode-title: {str(e)[:100]}")
            
            # Phương pháp 2: Thử tìm Thinking mode bằng data-test-id (tiếng Anh)
            try:
                thinking_button = self.driver.find_element(
                    By.CSS_SELECTOR, "button[data-test-id='bard-mode-option-thinking']"
                )
                
                # Kiểm tra xem có bị disabled không
                is_disabled = thinking_button.get_attribute("disabled") or thinking_button.get_attribute("aria-disabled") == "true"
                if not is_disabled:
                    self.driver.execute_script("arguments[0].click();", thinking_button)
                    self.log("✅ Đã chuyển sang Thinking mode (by data-test-id)")
                    time.sleep(1)
                    return True
            except:
                pass
            
            # Phương pháp 3: Thử tìm bằng partial match trong data-test-id
            try:
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test-id^='bard-mode-option-']")
                self.log(f"-> Tìm thấy {len(all_buttons)} mode buttons")
                for button in all_buttons:
                    test_id = button.get_attribute("data-test-id") or ""
                    if "thinking" in test_id.lower() or "duy" in test_id.lower():
                        is_disabled = button.get_attribute("disabled") or button.get_attribute("aria-disabled") == "true"
                        if not is_disabled:
                            self.driver.execute_script("arguments[0].click();", button)
                            self.log(f"✅ Đã chuyển sang Thinking mode (by test-id: {test_id})")
                            time.sleep(1)
                            return True
            except Exception as e:
                self.log(f"!!! Lỗi khi tìm buttons: {str(e)[:100]}")
            
            self.log("!!! Không tìm thấy Thinking/Tư duy mode hoặc mode đã bị giới hạn")
            return False
            
        except Exception as e:
            self.log(f"!!! Lỗi khi chuyển sang Thinking mode: {str(e)[:100]}")
            return False


def init_firefox_with_profile(firefox_profile, headless=False, log_func=None):
    """Shared function to initialize Firefox with profile and geckodriver.
    
    Uses the profile DIRECTLY (no temp copy) to preserve all browser data
    (localStorage, IndexedDB, cache, history) between runs.
    This makes the browser look like a real user's browser.
    
    Args:
        firefox_profile: Path to Firefox profile directory
        headless: Whether to run in headless mode
        log_func: Optional logging function
    
    Returns:
        (driver, None) - Firefox driver and None (no temp dir to cleanup)
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    log(">>> Đang khởi động Firefox...")
    log(f"-> Sử dụng profile trực tiếp: {firefox_profile}")
    
    if not os.path.exists(firefox_profile):
        raise FileNotFoundError(f"Profile không tồn tại: {firefox_profile}")
    
    # Remove lock file if exists (from previous crashed session)
    lock_file = os.path.join(firefox_profile, "parent.lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            log("-> Đã xóa parent.lock (từ session cũ)")
        except:
            log("-> ⚠️ Không thể xóa parent.lock, Firefox có thể đang chạy với profile này")
    
    # Init Firefox
    mode_str = "(headless)" if headless else "với GUI"
    log(f"\n>>> Khởi động Firefox {mode_str}...")
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.profile = firefox_profile
    
    # ========== HIDE SELENIUM AUTOMATION ==========
    # 1. Disable webdriver flag (navigator.webdriver = false)
    options.set_preference("dom.webdriver.enabled", False)
    
    # 2. Disable automation extension
    options.set_preference("useAutomationExtension", False)
    
    # 3. Disable Marionette logging
    options.set_preference("marionette.logging", False)
    
    # 4. Spoof user-agent to look like normal Firefox (not Selenium)
    # Use latest Firefox user-agent string
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
    options.set_preference("general.useragent.override", user_agent)
    
    # 5. Spoof navigator properties
    options.set_preference("general.platform.override", "Win32")
    options.set_preference("general.appversion.override", "5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0")
    options.set_preference("general.oscpu.override", "Windows NT 10.0; Win64; x64")
    options.set_preference("general.buildID.override", "20240101000000")
    
    # 6. Disable WebRTC leak (can reveal real IP)
    options.set_preference("media.peerconnection.enabled", False)
    options.set_preference("media.navigator.enabled", False)
    
    # 7. Disable geolocation
    options.set_preference("geo.enabled", False)
    
    # 8. Disable notifications
    options.set_preference("dom.webnotifications.enabled", False)
    
    # 9. Disable WebGL fingerprinting
    options.set_preference("webgl.disabled", True)
    
    # 9. Disable battery API
    options.set_preference("dom.battery.enabled", False)
    
    # 10. Disable gamepad API
    options.set_preference("dom.gamepad.enabled", False)
    
    # 11. Disable sensor APIs
    options.set_preference("device.sensors.enabled", False)
    
    # 12. Disable telemetry
    options.set_preference("toolkit.telemetry.enabled", False)
    options.set_preference("toolkit.telemetry.unified", False)
    options.set_preference("toolkit.telemetry.archive.enabled", False)
    
    # 13. Privacy settings
    options.set_preference("privacy.trackingprotection.enabled", True)
    options.set_preference("privacy.resistFingerprinting", False)  # True can break sites
    
    # 14. Disable safe browsing (can leak info to Google)
    options.set_preference("browser.safebrowsing.enabled", False)
    options.set_preference("browser.safebrowsing.malware.enabled", False)
    
    log("-> Đã ẩn dấu vết Selenium (14 settings)")
    
    # Find geckodriver in tools folder
    project_root = os.path.dirname(SCRIPT_DIR)
    tools_dir = os.path.join(project_root, "tools")
    geckodriver_path = None
    
    for root, dirs, files in os.walk(tools_dir):
        if "geckodriver.exe" in files:
            geckodriver_path = os.path.join(root, "geckodriver.exe")
            break
    
    if not geckodriver_path:
        raise FileNotFoundError(f"Không tìm thấy geckodriver.exe trong {tools_dir}")
    
    log(f">>> Sử dụng geckodriver: {geckodriver_path}")
    service = Service(geckodriver_path)
    driver = webdriver.Firefox(service=service, options=options)
    
    # ========== INJECT JAVASCRIPT TO HIDE WEBDRIVER ==========
    # Override navigator.webdriver after browser starts
    try:
        driver.execute_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override plugins (empty = detectable)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'vi']
            });
        """)
        log("-> Đã inject JS để ẩn webdriver")
    except Exception as e:
        log(f"-> Không thể inject JS: {e}")
    
    return driver, None
