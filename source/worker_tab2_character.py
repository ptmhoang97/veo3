"""
Tab 1: Character Appearance Worker
Tạo prompt và chạy Gemini để generate character appearance description
"""

import os
import re
import glob
import shutil
import tempfile
import time
import traceback

from worker_base import (
    WorkerThread, SELENIUM_AVAILABLE, SCRIPT_DIR,
    webdriver, By, Keys, Service, Options, GeckoDriverManager,
    WebDriverWait, EC, init_firefox_with_profile
)


class PrepareCharacterPromptWorker(WorkerThread):
    """Worker để tạo input prompt cho character appearance từ template + topic"""
    
    def __init__(self, topic, template_path, output_path):
        super().__init__()
        self.topic = topic
        self.template_path = template_path
        self.output_path = output_path
    
    def run(self):
        try:
            self.log("🚀 Preparing character appearance prompt...")
            self.log(f"📋 Topic: {self.topic}")
            self.log(f"📄 Template: {self.template_path}")
            self.log(f"📁 Output: {self.output_path}\n")
            
            # Read template
            template_name = os.path.basename(self.template_path)
            self.log(f"📖 Reading prompt template: {template_name}")
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            self.log(f"✅ Template loaded: {template_name}\n")
            
            # Replace topic placeholder using regex (generic - works with any text inside [])
            self.log("⚙️ Filling topic into template...")
            prompt = re.sub(
                r'(- TOPIC: )\[.*?\]',
                rf'\1[{self.topic}]',
                template
            )
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            # Save
            output_name = os.path.basename(self.output_path)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            self.log(f"✅ Prompt saved: {output_name}")
            self.log(f"📝 Content length: {len(prompt)} characters")
            
            self.finished_signal.emit(True, "Character prompt prepared successfully!")
            
        except Exception as e:
            self.log(f"\n❌ Error: {e}")
            self.log(traceback.format_exc())
            self.finished_signal.emit(False, str(e))


class RunCharacterGeminiWorker(WorkerThread):
    """Worker để chạy prompt character trên Gemini và lấy output"""
    
    def __init__(self, input_prompt_path, output_path, firefox_profile, gemini_url, hide_firefox=True, headless=False, 
                 timeout_seconds=300, auto_restart_on_timeout=True, gemini_mode='Pro'):
        super().__init__()
        self.input_prompt_path = input_prompt_path
        self.output_path = output_path
        self.firefox_profile = firefox_profile
        self.gemini_url = gemini_url
        self.hide_firefox = hide_firefox
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.auto_restart_on_timeout = auto_restart_on_timeout
        self.gemini_mode = gemini_mode
    
    def run(self):
        if not SELENIUM_AVAILABLE:
            self.log("❌ Selenium not installed!")
            self.finished_signal.emit(False, "Selenium not installed")
            return
        
        # Read prompt first (outside the loop)
        prompt_name = os.path.basename(self.input_prompt_path)
        self.log(f"📖 Reading prepared prompt: {prompt_name}")
        with open(self.input_prompt_path, 'r', encoding='utf-8') as f:
            prompt_text = f.read().strip()
        self.log(f"✅ Prompt loaded: {prompt_name} ({len(prompt_text)} characters)\n")
        
        if not prompt_text:
            self.finished_signal.emit(False, "Prompt file is empty!")
            return
        
        attempt = 0
        while not self._stop_requested:
            attempt += 1
            self.log(f"\n{'='*50}")
            self.log(f"🔄 Attempt {attempt}")
            self.log(f"{'='*50}")
            
            
            try:
                # Create temp profile
                self.driver, _ = init_firefox_with_profile(
                    self.firefox_profile,
                    self.headless,
                    self.log
                )
                
                # Ẩn/Hiện cửa sổ Firefox (không áp dụng cho headless)
                if not self.headless:
                    if self.hide_firefox:
                        self.driver.set_window_position(-10000, -10000)
                    else:
                        # Hiển thị Firefox window - đưa ra foreground
                        self.driver.set_window_size(1200, 800)
                        self.driver.set_window_position(100, 100)
                        try:
                            # Đưa window ra phía trước
                            self.driver.switch_to.window(self.driver.current_window_handle)
                            self.driver.execute_script("window.focus();")
                        except:
                            pass
                
                self.driver.get(self.gemini_url)
                time.sleep(5)
                
                self.log("✅ Firefox ready, đang gửi prompt tới Gemini...\n")
                
                # Count existing copy buttons
                COPY_BUTTON_SELECTOR = "copy-button"
                TEXT_CONTENT_SELECTOR = ".markdown.markdown-main-panel"
                
                old_buttons = self.driver.find_elements(By.CSS_SELECTOR, COPY_BUTTON_SELECTOR)
                old_count = len(old_buttons)
                
                # Send prompt
                input_box = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='textbox']"))
                )
                
                # Dismiss any overlay/popup (email opt-in, etc.) that may block the input
                try:
                    self.driver.execute_script("""
                        // Close any overlay/popup that might be blocking
                        var overlays = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, .overlay, .popup');
                        overlays.forEach(function(el) { el.remove(); });
                        // Click dismiss/close buttons if any
                        var closeButtons = document.querySelectorAll('button[aria-label="Close"], button[aria-label="Dismiss"], button[aria-label="No thanks"]');
                        closeButtons.forEach(function(btn) { btn.click(); });
                    """)
                    time.sleep(0.5)
                except:
                    pass
                
                # Use JavaScript click to bypass any remaining overlay
                try:
                    input_box.click()
                except:
                    self.log("-> Overlay detected, using JS click...")
                    self.driver.execute_script("arguments[0].click();", input_box)
                time.sleep(0.5)
                
                input_box.send_keys(Keys.CONTROL, "a")
                input_box.send_keys(Keys.DELETE)
                
                # Kiểm tra Pro mode trước khi gửi
                pro_status = self._ensure_pro_mode()
                
                if pro_status == 'LIMITED':
                    self.log("❌ Mode bị giới hạn, dừng lại!")
                    self.finished_signal.emit(False, "Gemini mode is limited")
                    return
                
                # Gửi prompt và verify
                if not self._send_prompt_and_verify(input_box, prompt_text):
                    self.log("❌ Không thể gửi prompt - browser giữ mở để debug")
                    self.finished_signal.emit(False, "Không thể gửi prompt")
                    return
                
                # Wait for response (có thể interrupt bởi stop)
                self.log(f"-> Đang chờ Gemini trả lời (timeout: {self.timeout_seconds}s)...")
                
                success, was_stopped = self._interruptible_wait(
                    lambda: len(self.driver.find_elements(By.CSS_SELECTOR, COPY_BUTTON_SELECTOR)) > old_count,
                    self.timeout_seconds
                )
                
                if was_stopped:
                    self.log("\n⏹️ Đã dừng theo yêu cầu")
                    self.finished_signal.emit(False, "Stopped by user")
                    return
                
                if success:
                    self.log("-> Nút Copy đã xuất hiện!")
                else:
                    self.log(f"!!! Hết giờ chờ (Timeout {self.timeout_seconds}s)")
                    if self.auto_restart_on_timeout:
                        self.log("⏱️ Timeout - browser giữ mở để debug")
                    else:
                        self.finished_signal.emit(False, "Timeout waiting for Gemini response")
                        return
                
                # Get content
                time.sleep(3)
                responses = self.driver.find_elements(By.CSS_SELECTOR, TEXT_CONTENT_SELECTOR)
                
                if responses:
                    final_text = responses[-1].text
                    
                    # Check for loading
                    retry = 0
                    while ("Loading" in final_text or len(final_text) < 5) and retry < 5:
                        self.log(f"   (Đợi thêm 2s - Lần {retry+1})")
                        time.sleep(2)
                        responses = self.driver.find_elements(By.CSS_SELECTOR, TEXT_CONTENT_SELECTOR)
                        final_text = responses[-1].text
                        retry += 1
                    
                    # Save result
                    output_name = os.path.basename(self.output_path)
                    os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
                    with open(self.output_path, 'w', encoding='utf-8') as f:
                        f.write(final_text)
                    
                    self.log(f"\n✅ Character appearance saved: {output_name}")
                    self.log(f"📁 Full path: {self.output_path}")
                    self.log(f"📝 Content ({len(final_text)} characters):\n")
                    self.log(final_text[:500] + ("..." if len(final_text) > 500 else ""))
                    
                    self.finished_signal.emit(True, "Character appearance generated successfully!")
                    return  # Success - exit loop
                else:
                    self.log("!!! Không tìm thấy response text")
                    self.finished_signal.emit(False, "No response from Gemini")
                    return  # Failed - exit loop
                    
            except Exception as e:
                self.log(f"\n❌ Error: {e}")
                self.log(traceback.format_exc())
                self.finished_signal.emit(False, str(e))
                return  # Error - exit loop
            finally:
                # Giữ browser mở để debug
                pass
