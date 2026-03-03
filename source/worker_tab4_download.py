"""
Tab 4: Download Videos Worker
Download tất cả videos đã hoàn thành từ Veo Flow
"""

import os
import shutil
import tempfile
import time
import traceback

from worker_base import (
    WorkerThread, SELENIUM_AVAILABLE,
    webdriver, By, ActionChains, Service, Options, GeckoDriverManager,
    WebDriverWait, EC, init_firefox_with_profile
)


class DownloadVideosWorker(WorkerThread):
    """Worker để download videos"""
    
    def __init__(self, veo_url, firefox_profile, wait_for_enter=False):
        super().__init__()
        self.veo_url = veo_url
        self.firefox_profile = firefox_profile
        self.wait_for_enter = wait_for_enter
    
    def run(self):
        if not SELENIUM_AVAILABLE:
            self.log("❌ Selenium not installed!")
            self.finished_signal.emit(False, "Selenium not installed")
            return
        
        
        try:
            # Init Firefox using centralized function
            self.driver, _ = init_firefox_with_profile(
                self.firefox_profile, False, self.log
            )
            
            # Open page
            self.log(f">>> Mở trang: {self.veo_url}")
            self.driver.get(self.veo_url)
            self.log("⏳ Đang đợi trang load...")
            time.sleep(15)
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
            
            # Download logic
            self.log("\n🚀 Bắt đầu quét và download videos...")
            self._download_all_videos()
            
            self.log("\n✅ Hoàn tất!")
            self.finished_signal.emit(True, "Download completed!")
            
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
    
    def _download_all_videos(self):
        """Scroll qua virtual list và download tất cả videos - TRACK THEO SCENE NUMBER"""
        try:
            # Tìm virtual scrolling container
            virtuoso_containers = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='virtuoso-item-list']")
            
            if not virtuoso_containers:
                self.log("❌ Không tìm thấy virtuoso container")
                return
            
            virtuoso_container = virtuoso_containers[0]
            self.log("✅ Tìm thấy virtuoso container")
            
            # Scroll về đầu
            self.driver.execute_script("""
                var container = arguments[0].parentElement.parentElement;
                container.scrollTop = 0;
            """, virtuoso_container)
            time.sleep(2)
            
            processed_scenes = set()
            scroll_attempts = 0
            max_scroll_attempts = 100
            consecutive_no_new = 0
            max_consecutive = 15
            total_videos_downloaded = 0
            item_count = 0
            
            self.log("\n📜 Đang quét và download videos...")
            
            while scroll_attempts < max_scroll_attempts and consecutive_no_new < max_consecutive:
                if self._stop_requested:
                    self.log("\n⚠️ Stopped by user")
                    break
                
                # Tìm tất cả items hiện đang visible
                items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
                
                found_new_scene = False
                
                for item in items:
                    if self._stop_requested:
                        break
                    try:
                        item_html = item.get_attribute("outerHTML")
                        
                        # Chỉ xử lý VIDEO_ITEM (không phải DATE_HEADER)
                        if "sc-333e51d6-0 fpoBvX" in item_html and "eMhQAG" not in item_html:
                            # Check nếu item có videos đã hoàn thành (không có %)
                            has_progress = False
                            try:
                                percent_divs = item.find_elements(By.CSS_SELECTOR, "div.sc-dd6abb21-1.iEQNVH")
                                if any('%' in div.text for div in percent_divs):
                                    has_progress = True
                            except:
                                pass
                            
                            # Chỉ download nếu không còn progress (đã hoàn thành)
                            if not has_progress and "Failed Generation" not in item_html:
                                # Lấy scene number từ prompt text
                                scene_number = None
                                try:
                                    prompt_button = item.find_element(By.CSS_SELECTOR, "button.sc-20145656-8")
                                    prompt_text = prompt_button.text
                                    if prompt_text.startswith("SCENE "):
                                        scene_part = prompt_text.split(":")[0]
                                        scene_number = int(scene_part.replace("SCENE ", ""))
                                except:
                                    pass
                                
                                # Skip nếu đã xử lý scene này
                                if scene_number and scene_number not in processed_scenes:
                                    found_new_scene = True
                                    item_count += 1
                                    
                                    self.log(f"\n   📹 Item #{item_count} - SCENE {scene_number}")
                                    videos_downloaded = self._download_videos_from_item(item, item_count, scene_number, virtuoso_container)
                                    
                                    # Chỉ add vào processed_scenes nếu download thành công
                                    if videos_downloaded > 0:
                                        processed_scenes.add(scene_number)
                                        total_videos_downloaded += videos_downloaded
                                    else:
                                        self.log(f"      ⚠️ SCENE {scene_number} không download được video nào, sẽ thử lại")
                                
                    except Exception as e:
                        continue
                
                if found_new_scene:
                    consecutive_no_new = 0
                else:
                    consecutive_no_new += 1
                
                # Scroll xuống
                self.driver.execute_script("""
                    var container = arguments[0].parentElement.parentElement;
                    container.scrollTop += 300;
                """, virtuoso_container)
                
                time.sleep(0.5)
                scroll_attempts += 1
            
            self.log(f"\n{'='*60}")
            self.log(f"✅ HOÀN THÀNH!")
            self.log(f"   📁 URL: {self.veo_url}")
            self.log(f"   Đã xử lý {item_count} prompt items")
            self.log(f"   Đã download {total_videos_downloaded} videos")
            if processed_scenes:
                sorted_scenes = sorted(processed_scenes)
                self.log(f"   Scenes: {min(sorted_scenes)}-{max(sorted_scenes)} (total: {len(sorted_scenes)} scenes)")
                missing_scenes = []
                if len(sorted_scenes) > 0:
                    for i in range(min(sorted_scenes), max(sorted_scenes) + 1):
                        if i not in processed_scenes:
                            missing_scenes.append(i)
                if missing_scenes:
                    self.log(f"   ⚠️ Missing scenes: {missing_scenes}")
            self.log(f"{'='*60}")
            
        except Exception as e:
            self.log(f"\n❌ Lỗi khi xử lý: {e}")
    
    def _download_videos_from_item(self, item, item_number, scene_number, virtuoso_container):
        """Download tất cả videos (2 videos) từ một prompt item với retry và stale element handling"""
        videos_downloaded = 0
        
        # Retry toàn bộ quá trình tìm + download (xử lý stale ở mọi bước)
        for full_retry in range(3):
            try:
                # Scroll item vào view
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                time.sleep(1)
                
                # Tìm tất cả download buttons trong item
                download_buttons = []
                buttons = item.find_elements(By.CSS_SELECTOR, "button[aria-haspopup='menu']")
                
                for btn in buttons:
                    try:
                        outer_html = btn.get_attribute("outerHTML")
                        if ">download<" in outer_html:
                            download_buttons.append(btn)
                    except:
                        continue
                
                self.log(f"      Tìm thấy {len(download_buttons)} download buttons")
                
                if not download_buttons:
                    self.log(f"      ⚠️ Không tìm thấy download buttons")
                    return 0
                
                # Download từng video
                for idx, btn in enumerate(download_buttons):
                    if self._stop_requested:
                        break
                    
                    # Retry tối đa 3 lần per button
                    success = False
                    for retry in range(3):
                        try:
                            # Scroll button vào view
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                            time.sleep(1)
                            
                            # Hover và click
                            ActionChains(self.driver).move_to_element(btn).perform()
                            time.sleep(0.5)
                            btn.click()
                            time.sleep(1)
                            
                            # Tìm và click option "Original size (720p)"
                            try:
                                original_option = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, "//div[@role='menuitem' and contains(text(), 'Original size (720p)')]"))
                                )
                                original_option.click()
                                self.log(f"      ✅ Đã download video {idx+1}/{len(download_buttons)}")
                                videos_downloaded += 1
                                success = True
                                time.sleep(2)
                                break  # Success, exit retry loop
                            except:
                                # Click ra ngoài để đóng menu
                                try:
                                    self.driver.find_element(By.TAG_NAME, "body").click()
                                except:
                                    pass
                                time.sleep(1)
                                
                        except Exception as e:
                            if "stale" in str(e).lower():
                                self.log(f"      ⚠️ Video {idx+1} - Element stale, đang relocate...")
                                if retry < 2:
                                    # Dùng scroll up/down để relocate
                                    relocated_item = self._relocate_scene(scene_number, virtuoso_container)
                                    if relocated_item:
                                        # Re-find buttons
                                        new_buttons = relocated_item.find_elements(By.CSS_SELECTOR, "button[aria-haspopup='menu']")
                                        button_found = []
                                        for new_btn in new_buttons:
                                            try:
                                                if ">download<" in new_btn.get_attribute("outerHTML"):
                                                    button_found.append(new_btn)
                                            except:
                                                continue
                                        if len(button_found) > idx:
                                            download_buttons[idx] = button_found[idx]
                                            btn = button_found[idx]
                                            self.log(f"      ✓ Re-found button {idx+1}")
                                    time.sleep(1)
                                else:
                                    self.log(f"      ❌ Video {idx+1} stale after 3 retries")
                            else:
                                if retry < 2:
                                    self.log(f"      ⚠️ Video {idx+1} retry {retry+1}/3")
                                    time.sleep(1)
                                else:
                                    self.log(f"      ❌ Video {idx+1} failed: {str(e)[:100]}")
                    
                    if not success:
                        self.log(f"      ⚠️ Skipping video {idx+1}")
                
                return videos_downloaded
                
            except Exception as e:
                # Stale element khi tìm buttons lần đầu
                if "stale" in str(e).lower() and full_retry < 2:
                    self.log(f"      ⚠️ Element stale (DOM changed), relocate lần {full_retry+1}/3...")
                    relocated_item = self._relocate_scene(scene_number, virtuoso_container)
                    if relocated_item:
                        item = relocated_item
                        time.sleep(1)
                        continue  # Retry toàn bộ
                    else:
                        self.log(f"      ❌ Không relocate được SCENE {scene_number}")
                        return 0
                else:
                    self.log(f"      ❌ Lỗi: {str(e)[:100]}")
                    return 0
        
        return videos_downloaded
    
    def _relocate_scene(self, scene_number, virtuoso_container):
        """Khi stale element: scroll UP tìm SCENE+1 (định vị), rồi scroll DOWN tìm lại SCENE hiện tại"""
        try:
            # Bước 1: Scroll UP tìm SCENE tiếp theo (số lớn hơn = ở trên)
            self.log(f"      🔍 Scroll up tìm SCENE {scene_number + 1} để định vị...")
            self.driver.execute_script("""
                var container = arguments[0].parentElement.parentElement;
                container.scrollTop -= 300;
            """, virtuoso_container)
            time.sleep(1)
            
            # Kiểm tra có tìm thấy SCENE+1 không
            found_anchor = False
            items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
            for item in items:
                try:
                    prompt_btn = item.find_element(By.CSS_SELECTOR, "button.sc-20145656-8")
                    if f"SCENE {scene_number + 1}:" in prompt_btn.text:
                        self.log(f"      ✓ Tìm thấy SCENE {scene_number + 1} (anchor)")
                        found_anchor = True
                        break
                except:
                    continue
            
            if not found_anchor:
                self.log(f"      ⚠️ Không tìm thấy SCENE {scene_number + 1}, thử scroll thêm...")
                # Scroll thêm lên nếu chưa tìm thấy
                self.driver.execute_script("""
                    var container = arguments[0].parentElement.parentElement;
                    container.scrollTop -= 300;
                """, virtuoso_container)
                time.sleep(1)
                
                items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
                for item in items:
                    try:
                        prompt_btn = item.find_element(By.CSS_SELECTOR, "button.sc-20145656-8")
                        if f"SCENE {scene_number + 1}:" in prompt_btn.text:
                            self.log(f"      ✓ Tìm thấy SCENE {scene_number + 1} (anchor)")
                            found_anchor = True
                            break
                    except:
                        continue
            
            # Bước 2: Scroll DOWN quay lại tìm SCENE hiện tại
            self.log(f"      ⬇️ Scroll down quay lại SCENE {scene_number}...")
            for scroll_try in range(5):
                self.driver.execute_script("""
                    var container = arguments[0].parentElement.parentElement;
                    container.scrollTop += 150;
                """, virtuoso_container)
                time.sleep(1)
                
                items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-item-index]")
                for item in items:
                    try:
                        prompt_btn = item.find_element(By.CSS_SELECTOR, "button.sc-20145656-8")
                        if f"SCENE {scene_number}:" in prompt_btn.text:
                            self.log(f"      ✓ Tìm lại SCENE {scene_number}!")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                            time.sleep(1)
                            return item  # Trả về item mới
                    except:
                        continue
            
            self.log(f"      ❌ Không tìm lại được SCENE {scene_number}")
            return None
        except Exception as e:
            self.log(f"      ❌ Relocate error: {str(e)[:80]}")
            return None
