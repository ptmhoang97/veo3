"""
Tab 2: Fill Gemini Worker
Tự động điền prompts vào Gemini và lưu kết quả
"""

import os
import glob
import shutil
import tempfile
import time
import traceback
import re

from worker_base import (
    WorkerThread, SELENIUM_AVAILABLE,
    webdriver, By, Keys, Service, Options, GeckoDriverManager,
    WebDriverWait, EC, init_firefox_with_profile
)


class FillGeminiWorker(WorkerThread):
    """Worker để auto fill Gemini"""
    
    def __init__(self, input_dir, output_file, firefox_profile, gemini_url, hide_firefox=True, headless=False, 
                 timeout_seconds=180, auto_restart_on_timeout=True, gemini_mode='Pro'):
        super().__init__()
        self.input_dir = input_dir
        self.output_file = output_file
        self.firefox_profile = firefox_profile
        self.gemini_url = gemini_url
        self.hide_firefox = hide_firefox
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.auto_restart_on_timeout = auto_restart_on_timeout
        self.gemini_mode = gemini_mode
        self.processed_files = set()  # Track completed files
    
    def _get_last_completed_scene(self):
        """Đọc file output để tìm scene cuối cùng đã hoàn thành (từ dưới lên)
        Returns: (last_scene_number, set of processed_files)
        
        CHÚ Ý: processed_files chỉ chứa các scene từ 1 đến last_scene,
        để không skip các scene số lớn hơn mà thực ra chưa hoàn thành."""
        last_scene = 0
        processed = set()
        
        if not os.path.exists(self.output_file):
            return 0, set()
        
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Tìm tất cả "=== SOURCE: prompt_video_sceneXX.txt ==="
            pattern = r'=== SOURCE: (prompt_video_scene(\d+)\.txt) ==='
            matches = re.findall(pattern, content)
            
            # Tìm scene CUỐI CÙNG trong file (từ dưới lên)
            # Đây là scene thực sự hoàn thành cuối cùng
            if matches:
                last_filename, last_scene_str = matches[-1]  # Lấy match cuối cùng
                last_scene = int(last_scene_str)
                
                # Chỉ thêm các scene từ 1 đến last_scene vào processed
                # Không thêm các scene > last_scene vì có thể là data cũ
                for filename, scene_num in matches:
                    scene_int = int(scene_num)
                    if scene_int <= last_scene:
                        processed.add(filename)
                
                self.log(f"📋 Đọc file output (từ dưới lên): Scene cuối cùng là SCENE {last_scene}")
                self.log(f"   → Sẽ tiếp tục từ SCENE {last_scene + 1}")
            
        except Exception as e:
            self.log(f"⚠️ Không đọc được file output: {e}")
        
        return last_scene, processed
    
    def run(self):
        if not SELENIUM_AVAILABLE:
            self.log("❌ Selenium not installed!")
            self.finished_signal.emit(False, "Selenium not installed")
            return
            
        
        try:
            # Load prompts
            folder_name = os.path.basename(self.input_dir)
            self.log(f"📂 Loading prompts from folder: {folder_name}")
            prompts = []
            file_names = []
            
            prompt_files = glob.glob(os.path.join(self.input_dir, "prompt_video_scene*.txt"))
            
            def extract_scene_number(fp):
                try:
                    base = os.path.basename(fp)
                    num = base.replace("prompt_video_scene", "").replace(".txt", "")
                    return int(num)
                except:
                    return 0
            
            prompt_files = sorted(prompt_files, key=extract_scene_number)
            
            for fp in prompt_files:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        prompts.append(content)
                        file_names.append(os.path.basename(fp))
            
            self.log(f"✅ Loaded {len(prompts)} prompts\n")
            
            if not prompts:
                self.finished_signal.emit(False, "No prompts found!")
                return
            
            # Check existing progress (để resume)
            last_scene, self.processed_files = self._get_last_completed_scene()
            if self.processed_files:
                self.log(f"📋 Tìm thấy tiến độ cũ: {len(self.processed_files)} scenes đã hoàn thành")
                self.log(f"▶️ Sẽ tiếp tục từ SCENE {last_scene + 1}\n")
            
            # Init Firefox using centralized function
            self.driver, _ = init_firefox_with_profile(
                self.firefox_profile, self.headless, self.log
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
            
            # Selectors
            COPY_BUTTON_SELECTOR = "copy-button"
            TEXT_CONTENT_SELECTOR = ".markdown.markdown-main-panel"
            
            need_restart = False
            
            # Process each prompt - sử dụng while để có thể retry scene
            i = 0
            while i < len(prompts):
                if self._stop_requested:
                    self.log("\n⚠️ Stopped by user")
                    break
                
                current_file = file_names[i]
                
                # Skip already processed files
                if current_file in self.processed_files:
                    self.log(f"\n--- [{i+1}/{len(prompts)}] ⏭️ Skip (đã xử lý): {current_file} ---")
                    i += 1  # Chuyển sang scene kế tiếp
                    continue
                
                # Check if need to restart browser
                if need_restart:
                    self.log("\n❌ Cần restart browser - giữ browser mở để debug")
                    self.finished_signal.emit(False, "Browser cần restart - giữ mở để debug")
                    return
                
                self.log(f"\n--- [{i+1}/{len(prompts)}] Đang xử lý: {current_file} ---")
                
                prompt_text = prompts[i]  # Lấy prompt tương ứng với index hiện tại
                
                # === SCENE 60: Copy trực tiếp, không cần fill Gemini ===
                if current_file == "prompt_video_scene60.txt":
                    self.log("-> Scene 60: Copy trực tiếp (không cần Gemini)")
                    output_filename = os.path.basename(self.output_file)
                    with open(self.output_file, "a", encoding="utf-8") as f:
                        f.write(f"=== SOURCE: {current_file} ===\n")
                        f.write(f"{prompt_text}\n")
                        f.write(f"{'='*40}\n\n")
                    self.processed_files.add(current_file)
                    self.log(f"-> Đã lưu: {output_filename} (direct copy, {len(prompt_text)} ký tự)")
                    self.log(f"   ✅ Progress: {len(self.processed_files)}/{len(prompts)} files")
                    i += 1
                    continue
                
                try:
                    # Count existing copy buttons
                    old_buttons = self.driver.find_elements(By.CSS_SELECTOR, COPY_BUTTON_SELECTOR)
                    old_count = len(old_buttons)
                    
                    # Send prompt
                    input_box = WebDriverWait(self.driver, 20).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='textbox']"))
                    )
                    input_box.click()
                    time.sleep(0.5)
                    
                    input_box.send_keys(Keys.CONTROL, "a")
                    input_box.send_keys(Keys.DELETE)
                    
                    # Verify prompt đã được điền
                    current_text = input_box.text
                    if len(current_text) < 10:
                        self.log(f"!!! Cảnh báo: Prompt có vẻ chưa được điền đầy đủ (length={len(current_text)})")
                    
                    # Kiểm tra Pro mode trước khi gửi
                    pro_status = self._ensure_pro_mode()
                    
                    if pro_status == 'LIMITED':
                        self.log("❌ Mode bị giới hạn, dừng lại!")
                        self.log(f"   Tiến độ: {len(self.processed_files)}/{len(prompts)} scenes đã hoàn thành")
                        self.finished_signal.emit(False, "Gemini mode is limited")
                        return
                    
                    # Gửi prompt và verify
                    if not self._send_prompt_and_verify(input_box, prompt_text):
                        self.log("❌ Không thể gửi prompt - browser giữ mở để debug")
                        self.finished_signal.emit(False, "Không thể gửi prompt")
                        return
                    
                    # Verify input box đã trống (prompt đã được submit)
                    try:
                        input_check = self.driver.find_element(By.CSS_SELECTOR, "div[role='textbox']")
                        input_text_after = input_check.text.strip()
                        if len(input_text_after) > 50:
                            self.log(f"!!! Cảnh báo: Input box vẫn còn text ({len(input_text_after)} chars)")
                        else:
                            self.log("-> ✓ Input box đã trống, prompt đã submit thành công")
                    except:
                        pass
                    
                    # Wait for response (có thể interrupt bởi stop)
                    self.log(f"-> Đang chờ Gemini trả lời (timeout: {self.timeout_seconds}s)...")
                    
                    success, was_stopped = self._interruptible_wait(
                        lambda: len(self.driver.find_elements(By.CSS_SELECTOR, COPY_BUTTON_SELECTOR)) > old_count,
                        self.timeout_seconds
                    )
                    
                    if was_stopped:
                        self.log("\n⏹️ Đã dừng theo yêu cầu")
                        break
                    
                    if not success:
                        self.log(f"!!! Hết giờ chờ (Timeout {self.timeout_seconds}s)")
                        self.log("⏱️ Timeout - browser giữ mở để debug")
                        self.finished_signal.emit(False, f"Timeout {self.timeout_seconds}s")
                        return
                    
                    self.log("-> Nút Copy đã xuất hiện!")
                    
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
                        output_filename = os.path.basename(self.output_file)
                        with open(self.output_file, "a", encoding="utf-8") as f:
                            f.write(f"=== SOURCE: {current_file} ===\n")
                            f.write(f"{final_text}\n")
                            f.write(f"{'='*40}\n\n")
                        
                        # Mark as processed
                        self.processed_files.add(current_file)
                        
                        self.log(f"-> Đã lưu kết quả: {output_filename} (source: {current_file}, {len(final_text)} ký tự)")
                        self.log(f"   ✅ Progress: {len(self.processed_files)}/{len(prompts)} files")
                        
                        # Chuyển sang scene kế tiếp
                        i += 1
                    else:
                        self.log(f"!!! Không tìm thấy text")
                        # Không tăng i, sẽ retry scene này
                        need_restart = True
                        continue
                        
                except Exception as e:
                    self.log(f"\n❌ Lỗi nghiêm trọng: {e}")
                    self.log(f"⛔ DỪNG xử lý!")
                    self.finished_signal.emit(False, f"Error: {e}")
                    return
            
            self.log(f"\n>>> HOÀN THÀNH! Đã xử lý {len(self.processed_files)}/{len(prompts)} files")
            self.finished_signal.emit(True, "Gemini fill completed!")
            
        except Exception as e:
            self.log(f"\n❌ Error: {e}")
            self.log(traceback.format_exc())
            self.finished_signal.emit(False, str(e))
        finally:
            # Giữ browser mở để kiểm tra
            # if self.driver:
            #     try:
            #         self.driver.quit()
            #     except:
            #         pass
            pass
