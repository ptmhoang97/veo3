"""
Tab 3: Auto Create Video Worker
Tự động tạo videos trên Google Veo Flow
"""

import os
import shutil
import tempfile
import time
import random
import traceback

from worker_base import (
    WorkerThread, SELENIUM_AVAILABLE,
    webdriver, By, Keys, ActionChains, Service, Options, GeckoDriverManager,
    WebDriverWait, EC, init_firefox_with_profile
)


class AutoCreateVideoWorker(WorkerThread):
    """Worker để auto create video trên Veo Flow"""
    
    def __init__(self, gemini_file, veo_url, firefox_profile, wait_for_enter=False, auto_restart_on_failure=True, timeout_seconds=600):
        super().__init__()
        self.gemini_file = gemini_file
        self.veo_url = veo_url
        self.firefox_profile = firefox_profile
        self.wait_for_enter = wait_for_enter
        self.auto_restart_on_failure = auto_restart_on_failure
        self.timeout_seconds = timeout_seconds
    
    def _init_browser(self):
        """Initialize Firefox browser using shared function."""
        self.driver, _ = init_firefox_with_profile(
            self.firefox_profile,
            headless=False,
            log_func=self.log
        )
        
        # Open page
        self.log(f">>> Mở trang: {self.veo_url}")
        self.driver.get(self.veo_url)
        self.log("⏳ Đang đợi trang load...")
        time.sleep(10)
        self.log("✅ Trang đã load xong")
        
        # Wait for enter if needed
        if self.wait_for_enter:
            self.log("\n>>> ⏸️ ĐANG TẠM DỪNG - Vui lòng đăng nhập trong browser")
            self.log(">>> Đợi 30 giây để bạn đăng nhập...")
            for i in range(30, 0, -1):
                if self._stop_requested:
                    break
                if i % 5 == 0:
                    self.log(f"   Còn {i}s...")
                time.sleep(1)
            self.log("✅ Tiếp tục xử lý...")
        else:
            self.log("\n⚠️ Tự động tiếp tục sau 5s...")
            time.sleep(5)
    
    def _close_browser(self):
        """Đóng browser hiện tại"""
        try:
            if self.driver:
                self.driver.quit()
                self.log("✅ Đã đóng browser")
        except Exception as e:
            self.log(f"⚠️ driver.quit() có lỗi: {e}")
        
        self.driver = None
        time.sleep(3)
    
    def run(self):
        if not SELENIUM_AVAILABLE:
            self.log("❌ Selenium not installed!")
            self.finished_signal.emit(False, "Selenium not installed")
            return
        
        try:
            self.log("="*50)
            self.log("  AUTO CREATE VIDEO VEO FLOW V2")
            self.log("="*50)
            
            # Load prompts from gemini file
            gemini_filename = os.path.basename(self.gemini_file)
            self.log(f"\n📖 Loading prompts from gemini results file: {gemini_filename}")
            prompts_dict = self._load_prompts()
            self.log(f"✅ Loaded {len(prompts_dict)} prompts from: {gemini_filename}\n")
            
            if not prompts_dict:
                self.finished_signal.emit(False, "No prompts loaded!")
                return
            
            # Init browser lần đầu using centralized function
            self.driver, _ = init_firefox_with_profile(
                self.firefox_profile, False, self.log
            )
            
            # Open page
            self.log(f">>> Mở trang: {self.veo_url}")
            self.driver.get(self.veo_url)
            
            # Cleanup and count scenes
            self.log("\n📊 Đang xử lý: Xóa Failed Generation và tìm SCENE...")
            scene_dict = self._cleanup_and_count_scenes()
            
            # Xác định scene tiếp theo cần generate
            if not scene_dict:
                next_scene = 1
                self.log(f"\n🎬 Chưa có scene nào, bắt đầu từ SCENE {next_scene}")
            else:
                max_scene = max(scene_dict.keys())
                next_scene = max_scene + 1
                self.log(f"\n🎬 Đã có {len(scene_dict)} scenes, tiếp tục với SCENE {next_scene}")
            
            # VÒNG LẶP CHÍNH
            scene_fail_count = 0  # Đếm số lần fail cho scene hiện tại
            max_retries_per_scene = 3  # Tối đa 3 lần (1 lần đầu + 2 retry)
            
            while next_scene in prompts_dict and not self._stop_requested:
                prompt_text = prompts_dict[next_scene]
                
                self.log(f"\n{'='*60}")
                self.log(f"   📹 Generate SCENE {next_scene} (attempt {scene_fail_count + 1}/{max_retries_per_scene})")
                self.log(f"{'='*60}")
                
                # Fill prompt và generate
                fill_ok = self._fill_prompt_and_generate(prompt_text, next_scene)
                
                if fill_ok:
                    # Monitor kết quả
                    success = self._wait_and_monitor_generation(next_scene, prompt_text, max_wait_time=300, check_interval=5)
                    
                    if success:
                        self.log(f"\n✅ SCENE {next_scene} hoàn thành thành công!")
                        scene_fail_count = 0
                        next_scene += 1
                        continue
                
                # Nếu tới đây = FAILED (fill failed hoặc generation failed)
                scene_fail_count += 1
                self.log(f"\n❌ SCENE {next_scene} FAILED! (attempt {scene_fail_count}/{max_retries_per_scene})")
                
                if scene_fail_count >= max_retries_per_scene:
                    # Đã thử 3 lần cho scene này
                    if self.auto_restart_on_failure:
                        self.log(f"\n🔄 SCENE {next_scene} đã FAILED {max_retries_per_scene} lần liên tiếp!")
                        self.log(f"🔄 RESTART BROWSER VÀ BẮT ĐẦU LẠI TỪ ĐẦU...")
                        self.log("\n" + "="*60)
                        
                        # Tắt browser
                        self._close_browser()
                        
                        # Mở browser mới (như bấm Run lại)
                        self._init_browser()
                        
                        # Cleanup và tìm scene (như bấm Run lại)
                        self.log("\n📊 Đang xử lý: Xóa Failed Generation và tìm SCENE...")
                        scene_dict = self._cleanup_and_count_scenes()
                        
                        if not scene_dict:
                            next_scene = 1
                            self.log(f"\n🎬 Chưa có scene nào, bắt đầu từ SCENE {next_scene}")
                        else:
                            max_scene = max(scene_dict.keys())
                            next_scene = max_scene + 1
                            self.log(f"\n🎬 Đã có {len(scene_dict)} scenes, tiếp tục với SCENE {next_scene}")
                        
                        scene_fail_count = 0  # Reset counter
                        self.log("="*60 + "\n")
                    else:
                        # Tính năng restart bị tắt → bỏ qua scene này
                        self.log(f"⚠️ Auto-restart đã tắt. Bỏ qua SCENE {next_scene}...")
                        scene_fail_count = 0
                        next_scene += 1
                else:
                    # Chưa đủ 3 lần → retry cùng scene
                    self.log(f"🔄 Sẽ retry SCENE {next_scene}...")
            
            # Thông báo khi hết prompts
            if next_scene not in prompts_dict and not self._stop_requested:
                self.log(f"\n🎉 ĐÃ HOÀN THÀNH TẤT CẢ! Đã generate đến SCENE {next_scene - 1}")
                self.log(f"   Không còn prompt nào trong file")
            
            self.log("\n✅ Hoàn tất!")
            self.finished_signal.emit(True, "Video creation completed!")
            
        except Exception as e:
            self.log(f"\n❌ Error: {e}")
            self.log(traceback.format_exc())
            self.finished_signal.emit(False, str(e))
        finally:
            # Giữ browser mở để kiểm tra
            # self._close_browser()
            pass
    
    def _load_prompts(self):
        """Load prompts from gemini results file"""
        prompts_dict = {}
        
        if not os.path.exists(self.gemini_file):
            filename = os.path.basename(self.gemini_file)
            self.log(f"⚠️ File not found: {filename}")
            self.log(f"   Full path: {self.gemini_file}")
            return prompts_dict
        
        try:
            with open(self.gemini_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = content.split("=== SOURCE: prompt_video_scene")
            
            for section in sections[1:]:
                try:
                    first_line = section.split("===")[0]
                    scene_number = int(first_line.replace(".txt", "").strip())
                    
                    lines = section.split("\n")
                    for line in lines:
                        line = line.strip()
                        if line.startswith(f"SCENE {scene_number}:"):
                            prompts_dict[scene_number] = line
                            break
                except:
                    continue
                    
        except Exception as e:
            filename = os.path.basename(self.gemini_file)
            self.log(f"⚠️ Error loading file {filename}: {e}")
        
        return prompts_dict
    
    def _cleanup_and_count_scenes(self):
        """Xóa Failed Generation và tìm tất cả VIDEO_ITEM với SCENE"""
        try:
            virtuoso_containers = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='virtuoso-item-list']")
            
            if not virtuoso_containers:
                self.log("   ⚠️ Không tìm thấy danh sách prompt items")
                return {}
            
            virtuoso_container = virtuoso_containers[0]
            self.log("   Tìm thấy virtuoso-item-list container")
            
            # Bước 1: Xóa tất cả Failed Generation items (tạm comment)
            # self._delete_all_failed_generations(virtuoso_container)
            
            # Scroll về đầu
            self.driver.execute_script("""
                var container = arguments[0].parentElement.parentElement;
                container.scrollTop = 0;
            """, virtuoso_container)
            time.sleep(2)
            
            # Bước 2: Tìm tất cả VIDEO_ITEM với SCENE
            scene_dict = self._scroll_to_find_all_scenes(virtuoso_container)
            
            # Scroll về đầu
            self.driver.execute_script("""
                var container = arguments[0].parentElement.parentElement;
                container.scrollTop = 0;
            """, virtuoso_container)
            time.sleep(2)
            
            return scene_dict
            
        except Exception as e:
            self.log(f"\n⚠️ Lỗi khi xử lý: {e}")
            return {}
    
    def _delete_all_failed_generations(self, virtuoso_container):
        """Scroll để tìm và xóa tất cả Failed Generation items"""
        deleted_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 50
        consecutive_no_deletion = 0
        
        self.log("\n🗑️ Đang tìm và xóa Failed Generation items...")
        
        while scroll_attempts < max_scroll_attempts and consecutive_no_deletion < 3:
            if self._stop_requested:
                break
                
            items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
            deleted_in_this_pass = False
            
            for item in items:
                try:
                    index_str = item.get_attribute("data-item-index")
                    if not index_str:
                        continue
                    
                    index = int(index_str)
                    item_html = item.get_attribute("outerHTML")
                    
                    if "Failed Generation" in item_html:
                        self.log(f"   Tìm thấy Failed Generation tại index={index}, đang xóa...")
                        if self._delete_failed_generation(item):
                            deleted_count += 1
                            deleted_in_this_pass = True
                            consecutive_no_deletion = 0
                            time.sleep(1)
                            # Scroll về đầu
                            self.driver.execute_script("""
                                var container = arguments[0].parentElement.parentElement;
                                container.scrollTop = 0;
                            """, virtuoso_container)
                            time.sleep(1)
                            break
                except:
                    continue
            
            if not deleted_in_this_pass:
                consecutive_no_deletion += 1
                self.driver.execute_script("""
                    var container = arguments[0].parentElement.parentElement;
                    container.scrollTop += 300;
                """, virtuoso_container)
                time.sleep(0.5)
            
            scroll_attempts += 1
        
        self.log(f"✅ Đã xóa {deleted_count} Failed Generation items\n")
        return deleted_count
    
    def _delete_failed_generation(self, item):
        """Xóa một prompt item có Failed Generation"""
        try:
            item_html = item.get_attribute("outerHTML")
            if "Failed Generation" not in item_html:
                return False
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
            time.sleep(0.5)
            
            menu_buttons = item.find_elements(By.CSS_SELECTOR, "button[aria-haspopup='menu']")
            menu_button = None
            
            for btn in menu_buttons:
                if "more_vert" in btn.get_attribute("innerHTML"):
                    menu_button = btn
                    break
            
            if menu_button:
                self.driver.execute_script("arguments[0].click();", menu_button)
                time.sleep(1)
                
                delete_option = self.driver.find_element(By.XPATH, "//div[@role='menuitem']//i[text()='delete']/parent::div")
                self.driver.execute_script("arguments[0].click();", delete_option)
                time.sleep(1)
                return True
            
            return False
        except Exception as e:
            self.log(f"      ⚠️ Lỗi khi xóa: {e}")
            return False
    
    def _scroll_to_find_all_scenes(self, virtuoso_container):
        """Scroll qua virtual list để tìm tất cả VIDEO_ITEM có SCENE"""
        scene_dict = {}
        seen_scenes = set()
        scroll_attempts = 0
        max_scroll_attempts = 30
        no_new_scene_count = 0
        
        self.log("📜 Đang scroll để tìm VIDEO_ITEM với SCENE...")
        
        while scroll_attempts < max_scroll_attempts and no_new_scene_count < 5:
            if self._stop_requested:
                break
                
            items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
            found_new_scene = False
            
            for item in items:
                try:
                    index_str = item.get_attribute("data-item-index")
                    if not index_str:
                        continue
                    
                    index = int(index_str)
                    
                    # Tìm SCENE text trong item (selector mới giống check progress)
                    # Scene text nằm trong div.sc-21e778e8-1.hxRvgy hoặc div.sc-55ebc859-6.dukARQ
                    try:
                        scene_divs = item.find_elements(By.CSS_SELECTOR, "div.sc-21e778e8-1.hxRvgy, div.sc-55ebc859-6.dukARQ")
                        for div in scene_divs:
                            text = div.text
                            if text.startswith("SCENE "):
                                scene_part = text.split(":")[0]
                                scene_number = int(scene_part.replace("SCENE ", ""))
                                
                                if scene_number not in seen_scenes:
                                    seen_scenes.add(scene_number)
                                    scene_dict[scene_number] = index
                                    self.log(f"   Tìm thấy SCENE {scene_number} tại index={index}")
                                    found_new_scene = True
                                break
                    except:
                        pass
                except:
                    continue
            
            if not found_new_scene:
                no_new_scene_count += 1
            else:
                no_new_scene_count = 0
            
            self.driver.execute_script("""
                var container = arguments[0].parentElement.parentElement;
                container.scrollTop += 300;
            """, virtuoso_container)
            time.sleep(0.5)
            scroll_attempts += 1
        
        self.log(f"\n📋 Tổng kết: Tìm thấy {len(scene_dict)} SCENE")
        for scene_num in sorted(scene_dict.keys()):
            self.log(f"     - SCENE {scene_num} (index={scene_dict[scene_num]})")
        
        return scene_dict
    
    def _human_delay(self, min_sec=2, max_sec=4):
        """Tạo delay ngẫu nhiên giống con người"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def _human_type(self, element, text, typing_speed_range=(0.05, 0.15)):
        """Gõ text từng ký tự với tốc độ ngẫu nhiên"""
        for char in text:
            if self._stop_requested:
                break
            element.send_keys(char)
            time.sleep(random.uniform(*typing_speed_range))
    
    def _fill_prompt_and_generate(self, prompt_text, scene_number):
        """Điền prompt vào textarea và click button Generate"""
        try:
            self.log(f"\n🎬 Đang generate SCENE {scene_number}...")
            
            # ========== BƯỚC 0: Thiết lập các options ==========
            self.log(f"   📋 Đang thiết lập options...")
            
            # 0.1) Click vào General Option dropdown (Video button)
            try:
                general_option_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-haspopup='menu'].sc-46973129-1"))
                )
                general_option_btn.click()
                self._human_delay(1, 2)
                self.log(f"      ✅ Đã click General Option dropdown")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy General Option dropdown: {e}")
            
            # 0.2) Chọn tab Video
            try:
                video_tab = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[role='tab'][id*='VIDEO']:not([id*='REFERENCES'])"))
                )
                video_tab.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã chọn Video tab")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy Video tab: {e}")
            
            # 0.3) Chọn tab Ingredients
            try:
                ingredients_tab = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[role='tab'][id*='VIDEO_REFERENCES']"))
                )
                ingredients_tab.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã chọn Ingredients tab")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy Ingredients tab: {e}")
            
            # 0.4) Chọn Landscape (Ngang)
            try:
                landscape_tab = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[role='tab'][id*='LANDSCAPE']"))
                )
                landscape_tab.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã chọn Landscape (Ngang)")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy Landscape tab: {e}")
            
            # 0.5) Chọn x2
            try:
                x2_tab = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@role='tab' and contains(text(), 'x2')]"))
                )
                x2_tab.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã chọn x2")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy x2 tab: {e}")
            
            # 0.6) Chọn Model có [Lower Priority]
            try:
                # Click dropdown model
                model_dropdown = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-a0dcecfb-1[aria-haspopup='menu']"))
                )
                model_dropdown.click()
                self._human_delay(0.5, 1)
                
                # Chọn option có [Lower Priority]
                model_option = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'sc-a0dcecfb-8') and contains(text(), 'Lower Priority')]/ancestor::button"))
                )
                model_option.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã chọn Model có [Lower Priority]")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy Model dropdown: {e}")
            
            # 0.7) Click View Mode settings button
            try:
                view_mode_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-3fc3f9ed-4[aria-haspopup='menu']"))
                )
                view_mode_btn.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã click View Mode settings")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy View Mode button: {e}")
            
            # 0.8) Chọn Batch option
            try:
                batch_tab = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[role='tab'][id*='batch']"))
                )
                batch_tab.click()
                self._human_delay(0.5, 1)
                self.log(f"      ✅ Đã chọn Batch mode")
            except Exception as e:
                self.log(f"      ⚠️ Không tìm thấy Batch tab: {e}")
            
            self.log(f"   ✅ Đã thiết lập xong options")
            self._human_delay(1, 2)
            
            # ========== BƯỚC 1: Tìm và click vào textarea (Slate editor) ==========
            textarea = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='textbox'][data-slate-editor='true']"))
            )
            textarea.click()
            self._human_delay(1, 2)
            self.log(f"   ✅ Đã click vào input box")
            
            # ========== BƯỚC 2: Xóa nội dung cũ ==========
            textarea.send_keys(Keys.CONTROL, "a")
            self._human_delay(0.5, 1)
            self.log(f"   ✅ Đã select all")
            
            textarea.send_keys(Keys.DELETE)
            self._human_delay(0.5, 1)
            self.log(f"   ✅ Đã xóa nội dung cũ")
            
            # ========== BƯỚC 3: Điền prompt - gõ từng ký tự ==========
            self.log(f"   ⌨️ Đang gõ prompt ({len(prompt_text)} ký tự)...")
            self._human_type(textarea, prompt_text, typing_speed_range=(0.01, 0.03))
            self.log(f"   ✅ Đã điền prompt")
            self._human_delay(2, 4)
            
            # ========== BƯỚC 4: Click Generate button ==========
            # Tìm button có icon arrow_forward và span "Tạo"
            generate_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-21faa80e-4"))
            )
            generate_button.click()
            self.log(f"   ✅ Đã click Generate")
            self._human_delay(3, 5)
            
            return True
            
        except Exception as e:
            self.log(f"   ⚠️ Lỗi khi generate: {e}")
            return False
    
    def _wait_and_monitor_generation(self, scene_number, prompt_text, max_wait_time=300, check_interval=5):
        """Monitor generation progress. Return True nếu thành công, False nếu failed.
        KHÔNG retry bên trong - main loop sẽ xử lý retry."""
        self.log(f"\n⏱️ Bắt đầu monitor SCENE {scene_number} (max {max_wait_time}s)...")
        
        start_time = time.time()
        has_seen_progress = False
        
        while (time.time() - start_time) < max_wait_time and not self._stop_requested:
            time.sleep(check_interval)
            elapsed = int(time.time() - start_time)
            
            try:
                virtuoso_containers = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='virtuoso-item-list']")
                if not virtuoso_containers:
                    continue
                
                virtuoso_container = virtuoso_containers[0]
                
                # Scroll về đầu
                self.driver.execute_script("""
                    var container = arguments[0].parentElement.parentElement;
                    container.scrollTop = 0;
                """, virtuoso_container)
                time.sleep(1)
                
                items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
                
                for item in items:
                    try:
                        item_html = item.get_attribute("outerHTML")
                        
                        # Tìm SCENE text trong item (selector mới)
                        # Scene text nằm trong div.sc-21e778e8-1.hxRvgy hoặc div.sc-55ebc859-6.dukARQ
                        scene_text = ""
                        try:
                            scene_divs = item.find_elements(By.CSS_SELECTOR, "div.sc-21e778e8-1.hxRvgy, div.sc-55ebc859-6.dukARQ")
                            for div in scene_divs:
                                text = div.text
                                if text.startswith(f"SCENE {scene_number}:"):
                                    scene_text = text
                                    break
                        except:
                            pass
                        
                        if scene_text.startswith(f"SCENE {scene_number}:"):
                            # CHECK 1: Failed Generation → "Không thành công" (tạm comment)
                            # if "Không thành công" in item_html:
                            #     self.log(f"\n      ❌ SCENE {scene_number} bị Không thành công!")
                            #     # Xóa failed generation trước khi return
                            #     self._delete_failed_generation(item)
                            #     time.sleep(2)
                            #     return False
                            
                            # CHECK 2: Progress % - selector mới: div.sc-55ebc859-7.kAxcVK
                            try:
                                percent_divs = item.find_elements(By.CSS_SELECTOR, "div.sc-55ebc859-7.kAxcVK")
                                current_percentages = [div.text for div in percent_divs if '%' in div.text]
                                
                                if current_percentages:
                                    has_seen_progress = True
                                    try:
                                        percent_values = [int(p.replace('%', '')) for p in current_percentages]
                                        avg_percent = sum(percent_values) // len(percent_values)
                                        self.log(f"      📊 Progress: {avg_percent}% [{elapsed}s]")
                                    except:
                                        self.log(f"      📊 Progress: {', '.join(current_percentages)} [{elapsed}s]")
                                else:
                                    if has_seen_progress:
                                        self.log(f"      📊 Progress: 100% [{elapsed}s]")
                                        self.log(f"      ✅ SCENE {scene_number} hoàn thành!")
                                        
                                        # Download videos
                                        self.log(f"      📥 Đang download videos...")
                                        self._download_videos_for_scene(item, scene_number)
                                        return True
                            except:
                                pass
                            
                            break
                    except:
                        continue
                        
            except Exception as e:
                continue
        
        self.log(f"\n⏰ Hết thời gian monitor SCENE {scene_number}")
        return False
    
    def _download_videos_for_scene(self, scene_item, scene_number=None):
        """Download ALL videos trong scene với workflow: right-click → rename → right-click → download 720p"""
        try:
            # Scroll scene item vào giữa màn hình
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", scene_item)
            time.sleep(1)
            
            # Do virtual list, cần tìm lại item sau khi scroll
            # Dùng cùng cách với check progress: tìm div[data-item-index] chứa SCENE text
            target_item = None
            
            items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
            for item in items:
                try:
                    # Tìm SCENE text trong item (giống check progress)
                    scene_divs = item.find_elements(By.CSS_SELECTOR, "div.sc-21e778e8-1.hxRvgy, div.sc-55ebc859-6.dukARQ")
                    for div in scene_divs:
                        text = div.text
                        if text.startswith(f"SCENE {scene_number}:"):
                            target_item = item
                            break
                    if target_item:
                        break
                except:
                    continue
            
            if not target_item:
                self.log(f"         ⚠️ Không tìm lại được item SCENE {scene_number} sau scroll")
                target_item = scene_item  # Fallback
            
            # Scroll target_item vào giữa
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_item)
            time.sleep(0.5)
            
            # Tìm TẤT CẢ video elements (div[data-tile-id]) trong item
            # Lưu tile_ids thay vì element references (tránh StaleElementReferenceError)
            all_tiles = target_item.find_elements(By.CSS_SELECTOR, "div[data-tile-id]")
            
            # Lấy danh sách unique tile_ids
            tile_ids = []
            seen_tile_ids = set()
            
            for tile in all_tiles:
                try:
                    tile_id = tile.get_attribute("data-tile-id")
                    if tile_id and tile_id not in seen_tile_ids:
                        # Chỉ thêm nếu tile này KHÔNG chứa tile con khác (leaf node)
                        nested_tiles = tile.find_elements(By.CSS_SELECTOR, "div[data-tile-id]")
                        if len(nested_tiles) == 0:
                            seen_tile_ids.add(tile_id)
                            tile_ids.append(tile_id)
                except:
                    continue
            
            if not tile_ids:
                # Fallback: lấy tất cả unique tile_ids
                for tile in all_tiles:
                    try:
                        tile_id = tile.get_attribute("data-tile-id")
                        if tile_id and tile_id not in seen_tile_ids:
                            seen_tile_ids.add(tile_id)
                            tile_ids.append(tile_id)
                    except:
                        continue
            
            total_videos = len(tile_ids)
            if total_videos == 0:
                self.log(f"         ⚠️ Không tìm thấy video tiles")
                return
            
            self.log(f"         🎬 Tìm thấy {total_videos} video(s) trong SCENE {scene_number}")
            
            # Loop qua từng tile_id để rename và download
            for video_idx, tile_id in enumerate(tile_ids):
                if self._stop_requested:
                    break
                
                # Tên video: Tất cả đều cùng tên SCENE X
                video_name = f"SCENE {scene_number}"
                
                self.log(f"\n         📹 Video {video_idx + 1}/{total_videos}: {video_name}")
                
                # Tìm lại element (fresh reference)
                self.log(f"            🔍 Tìm video element với tile_id: {tile_id[:20]}...")
                video_element = self.driver.find_element(By.CSS_SELECTOR, f"div[data-tile-id='{tile_id}']")
                
                # Scroll vào view video element
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", video_element)
                time.sleep(1)
                
                # ========== RENAME ==========
                self.log(f"            📝 Bước 1: Rename → '{video_name}'")
                
                # Right-click
                self.log("               1. Right-click...")
                actions = ActionChains(self.driver)
                actions.move_to_element(video_element).perform()
                time.sleep(0.3)
                actions.context_click(video_element).perform()
                time.sleep(1)
                
                # Click "Đổi tên"
                self.log("               2. Click 'Đổi tên'...")
                try:
                    rename_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@role='menuitem' and contains(., 'Đổi tên')]"))
                    )
                    rename_option.click()
                    time.sleep(1)
                except Exception as e:
                    self.log(f"               ❌ Không tìm thấy 'Đổi tên': {e}")
                    continue
                
                # Nhập tên
                self.log("               3. Nhập tên mới...")
                try:
                    # Selector chính xác từ HTML: dialog có class sc-11801678-1, input có class sc-50a26567-2
                    name_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 
                            "div[role='dialog'].sc-11801678-1 input.sc-50a26567-2"))
                    )
                    
                    # Click bằng ActionChains
                    actions = ActionChains(self.driver)
                    actions.move_to_element(name_input).click().perform()
                    time.sleep(0.3)
                    
                    # Select all và gõ tên mới
                    name_input.send_keys(Keys.CONTROL + "a")
                    time.sleep(0.1)
                    name_input.send_keys(video_name)
                    time.sleep(0.5)
                    self.log(f"               ✅ Đã nhập: {video_name}")
                except Exception as e:
                    self.log(f"               ❌ Lỗi nhập tên: {e}")
                    continue
                
                # Enter để confirm
                self.log("               4. Bấm Enter...")
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ENTER).perform()
                time.sleep(1)
                self.log("               ✅ Đã bấm Enter")
                
                # ========== DOWNLOAD ==========
                self.log(f"            📥 Bước 2: Download 720p")
                
                # Scroll lại
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", video_element)
                time.sleep(0.5)
                
                # Right-click
                self.log("               1. Right-click...")
                actions = ActionChains(self.driver)
                actions.move_to_element(video_element).perform()
                time.sleep(0.3)
                actions.context_click(video_element).perform()
                time.sleep(1)
                
                # Click "Tải xuống"
                self.log("               2. Click 'Tải xuống'...")
                try:
                    download_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[@role='menuitem' and contains(., 'Tải xuống')]"))
                    )
                    actions = ActionChains(self.driver)
                    actions.move_to_element(download_option).perform()
                    time.sleep(0.5)
                    download_option.click()
                    time.sleep(0.5)
                except Exception as e:
                    self.log(f"               ❌ Không tìm thấy 'Tải xuống': {e}")
                    continue
                
                # Click 720p
                self.log("               3. Click '720p'...")
                try:
                    resolution_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@role='menuitem' and .//span[contains(text(), '720p')]]"))
                    )
                    resolution_option.click()
                    time.sleep(1)
                    self.log("               ✅ Download started!")
                except Exception as e:
                    self.log(f"               ❌ Không tìm thấy 720p: {e}")
                    continue
                
                self.log(f"\n            ✅ Video {video_idx + 1} xong!")
                time.sleep(1)
            
            self.log(f"\n         ✅ Download hoàn tất cho SCENE {scene_number} ({total_videos} videos)!")
                    
        except Exception as e:
            self.log(f"         ❌ Download error: {e}")
            self._close_any_menu()
    
    def _close_any_menu(self):
        """Đóng bất kỳ menu nào đang mở"""
        try:
            # Press Escape để đóng menu
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.ESCAPE).perform()
            time.sleep(0.3)
        except:
            pass
        try:
            # Click body để đóng menu
            self.driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(0.3)
        except:
            pass
