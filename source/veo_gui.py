"""
VEO VIDEO AUTOMATION GUI
Main GUI - imports workers từ các file riêng biệt
"""

import sys
import os
import configparser

# Đảm bảo source/ nằm trong sys.path (cho embedded Python)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTextEdit, QLineEdit,
    QFileDialog, QMessageBox, QGroupBox, QGridLayout, QCheckBox,
    QScrollArea, QDialog, QSizePolicy, QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor

from worker_base import SELENIUM_AVAILABLE, SCRIPT_DIR, BASE_DIR
from worker_tab1_voiceover import PrepareVoiceoverPromptWorker, RunVoiceoverGeminiWorker
from worker_tab2_character import PrepareCharacterPromptWorker, RunCharacterGeminiWorker
from worker_tab3_1_create_prompts import CreatePromptsWorker
from worker_tab3_2_fill_gemini import FillGeminiWorker
from worker_tab3_3_create_video import AutoCreateVideoWorker
from worker_tab4_download import DownloadVideosWorker
from worker_tab5_review import ReviewVideosDialog


class SettingsDialog(QDialog):
    """Pop-up Dialog cho Settings"""
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Settings - Web URLs & File Paths")
        self.setModal(True)
        self.setMinimumSize(800, 650)
        
        self.config = config
        self.load_current_config()  # Auto-load config.ini if exists
        self.setup_ui()
    
    def load_current_config(self):
        """Load config từ config.ini nếu tồn tại"""
        config_parser = configparser.ConfigParser()
        config_path = os.path.join(SCRIPT_DIR, "config.ini")
        
        if os.path.exists(config_path):
            config_parser.read(config_path, encoding='utf-8')
            
            # Update self.config với values từ config.ini
            if 'Prompt' in config_parser:
                self.config['topic'] = config_parser['Prompt'].get('topic', self.config.get('topic', ''))
                self.config['language'] = config_parser['Prompt'].get('language', self.config.get('language', 'English'))

            
            if 'URLs' in config_parser:
                self.config['gemini_url'] = config_parser['URLs'].get('gemini_url', self.config['gemini_url'])
                self.config['veo_url'] = config_parser['URLs'].get('veo_url', self.config['veo_url'])
            
            if 'Firefox' in config_parser:
                self.config['profile_path'] = config_parser['Firefox'].get('profile_path', self.config['profile_path'])
            
            if 'Browser' in config_parser:
                self.config['gemini_mode'] = config_parser['Browser'].get('gemini_mode', self.config.get('gemini_mode', 'Pro'))
                self.config['timeout_seconds'] = config_parser['Browser'].get('timeout_seconds', self.config.get('timeout_seconds', '180'))
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # === Prompt Input section ===
        prompt_group = QGroupBox("📝 Prompt Input")
        prompt_layout = QGridLayout()
        
        prompt_layout.addWidget(QLabel("Topic:"), 0, 0)
        self.topic = QLineEdit(self.config.get('topic', ''))
        self.topic.setPlaceholderText("VD: Richard Branson thành lập Virgin Atlantic")
        prompt_layout.addWidget(self.topic, 0, 1)
        
        prompt_layout.addWidget(QLabel("Language:"), 1, 0)
        self.language = QLineEdit(self.config.get('language', 'English'))
        self.language.setPlaceholderText("VD: English, Vietnamese, Japanese...")
        prompt_layout.addWidget(self.language, 1, 1)
        

        
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)
        
        # === Web URLs section ===
        urls_group = QGroupBox("🌐 Web URLs")
        urls_layout = QGridLayout()
        
        urls_layout.addWidget(QLabel("Gemini URL:"), 0, 0)
        self.gemini_url = QLineEdit(self.config['gemini_url'])
        urls_layout.addWidget(self.gemini_url, 0, 1)
        
        urls_layout.addWidget(QLabel("Flow URL:"), 1, 0)
        self.veo_url = QLineEdit(self.config['veo_url'])
        urls_layout.addWidget(self.veo_url, 1, 1)
        
        urls_layout.addWidget(QLabel("Firefox Profile Folder:"), 2, 0)
        self.firefox_profile = QLineEdit(self.config['profile_path'])
        self.firefox_profile.setPlaceholderText("VD: wo0vat7e.veo (folder trong tools/profiles/)")
        urls_layout.addWidget(self.firefox_profile, 2, 1)
        
        urls_group.setLayout(urls_layout)
        layout.addWidget(urls_group)
        
        # === File Paths section ===
        files_group = QGroupBox("📁 File Paths")
        files_layout = QGridLayout()
        
        row = 0
        files_layout.addWidget(QLabel("Prompt Template:"), row, 0)
        self.template_path = QLineEdit(os.path.join(SCRIPT_DIR, "prompt_base", "prompt_3_video_scenes_story.txt"))
        files_layout.addWidget(self.template_path, row, 1)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse_file(self.template_path))
        files_layout.addWidget(btn, row, 2)
        row += 1
        
        files_layout.addWidget(QLabel("Character Description:"), row, 0)
        self.character_path = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "2_character_appearance", "output_prompt_character_appearance.txt"))
        files_layout.addWidget(self.character_path, row, 1)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse_file(self.character_path))
        files_layout.addWidget(btn, row, 2)
        row += 1
        
        files_layout.addWidget(QLabel("Script Scenes:"), row, 0)
        self.script_path = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "1_voiceover_60scenes", "output_prompt_voiceover_60scenes.txt"))
        files_layout.addWidget(self.script_path, row, 1)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse_file(self.script_path))
        files_layout.addWidget(btn, row, 2)
        row += 1
        
        files_layout.addWidget(QLabel("Output Folder:"), row, 0)
        self.output_path = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "3.1_prompt_video_60scenes_for_gemini"))
        files_layout.addWidget(self.output_path, row, 1)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse_folder(self.output_path))
        files_layout.addWidget(btn, row, 2)
        row += 1
        
        files_layout.addWidget(QLabel("Gemini Results:"), row, 0)
        self.gemini_output = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "3.2_prompt_video_60scenes_for_veo3", "prompt_video_60scenes.txt"))
        files_layout.addWidget(self.gemini_output, row, 1)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse_file(self.gemini_output))
        files_layout.addWidget(btn, row, 2)
        
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)
        
        # === Browser Options section ===
        browser_group = QGroupBox("🌐 Browser Options")
        browser_layout = QVBoxLayout()
        
        self.wait_for_enter_tab3 = QCheckBox("⏸️ [Tab 3] Tạm dừng 30s sau khi mở browser (để đăng nhập)")
        browser_layout.addWidget(self.wait_for_enter_tab3)
        
        self.wait_for_enter_tab4 = QCheckBox("⏸️ [Tab 4] Tạm dừng 30s sau khi mở browser (để đăng nhập)")
        browser_layout.addWidget(self.wait_for_enter_tab4)
        
        self.auto_restart_on_failure = QCheckBox("🔄 [Tab 3] Tự động restart browser sau 3 lần failed liên tiếp")
        self.auto_restart_on_failure.setChecked(True)
        browser_layout.addWidget(self.auto_restart_on_failure)
        
        # Auto restart on timeout
        self.auto_restart_on_timeout = QCheckBox("⏱️ Tự động restart browser khi timeout và tiếp tục từ vị trí dừng")
        self.auto_restart_on_timeout.setChecked(True)
        browser_layout.addWidget(self.auto_restart_on_timeout)
        
        # Timeout seconds setting
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("⏰ Timeout (giây):"))
        self.timeout_seconds = QSpinBox()
        self.timeout_seconds.setMinimum(30)
        self.timeout_seconds.setMaximum(600)
        self.timeout_seconds.setValue(int(self.config.get('timeout_seconds', '180')))
        self.timeout_seconds.setSuffix(" s")
        timeout_layout.addWidget(self.timeout_seconds)
        timeout_layout.addStretch()
        browser_layout.addLayout(timeout_layout)
        
        # Gemini Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("🤖 Gemini Mode:"))
        self.gemini_mode = QComboBox()
        self.gemini_mode.addItems(["Pro", "Thinking (Tư duy)"])
        current_mode = self.config.get('gemini_mode', 'Pro')
        if "thinking" in current_mode.lower() or "tư duy" in current_mode.lower():
            self.gemini_mode.setCurrentIndex(1)
        else:
            self.gemini_mode.setCurrentIndex(0)
        mode_layout.addWidget(self.gemini_mode)
        mode_layout.addStretch()
        browser_layout.addLayout(mode_layout)
        
        browser_group.setLayout(browser_layout)
        layout.addWidget(browser_group)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Buttons at bottom
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Save Config")
        save_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        reload_btn = QPushButton("🔄 Reload Config")
        reload_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        reload_btn.setMinimumHeight(40)
        reload_btn.clicked.connect(self.reload_config)
        button_layout.addWidget(reload_btn)
        
        close_btn = QPushButton("✖️ Close")
        close_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        close_btn.setMinimumHeight(40)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def browse_file(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            line_edit.setText(path)
    
    def browse_folder(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            line_edit.setText(path)
    
    def save_config(self):
        """Lưu config vào file config.ini"""
        config = configparser.ConfigParser()
        config['Prompt'] = {
            'topic': self.topic.text(),
            'language': self.language.text(),

        }
        config['URLs'] = {
            'gemini_url': self.gemini_url.text(),
            'veo_url': self.veo_url.text()
        }
        config['Firefox'] = {
            'profile_path': self.firefox_profile.text()
        }
        config['Browser'] = {
            'gemini_mode': self.gemini_mode.currentText(),
            'timeout_seconds': str(self.timeout_seconds.value())
        }
        
        config_path = os.path.join(SCRIPT_DIR, "config.ini")
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
        
        QMessageBox.information(self, "Success", "✅ Config saved to config.ini")
    
    def reload_config(self):
        """Reload config từ file config.ini"""
        config = configparser.ConfigParser()
        config_path = os.path.join(SCRIPT_DIR, "config.ini")
        
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
            
            if 'Prompt' in config:
                self.topic.setText(config['Prompt'].get('topic', ''))
                self.language.setText(config['Prompt'].get('language', 'English'))

            
            if 'URLs' in config:
                self.gemini_url.setText(config['URLs'].get('gemini_url', ''))
                self.veo_url.setText(config['URLs'].get('veo_url', ''))
            
            if 'Firefox' in config:
                self.firefox_profile.setText(config['Firefox'].get('profile_path', ''))
            
            if 'Browser' in config:
                mode = config['Browser'].get('gemini_mode', 'Pro')
                if "thinking" in mode.lower() or "tư duy" in mode.lower():
                    self.gemini_mode.setCurrentIndex(1)
                else:
                    self.gemini_mode.setCurrentIndex(0)
                self.timeout_seconds.setValue(int(config['Browser'].get('timeout_seconds', '180')))
            
            QMessageBox.information(self, "Success", "✅ Config reloaded from config.ini")
        else:
            QMessageBox.warning(self, "Warning", "⚠️ config.ini not found")


class VeoGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VEO Video Automation Suite")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_worker = None
        self.is_running = False
        
        # Default settings for timeout/auto-restart (will be overwritten by SettingsDialog)
        self._timeout_seconds = 300
        self._auto_restart_on_timeout = True
        
        # Load config
        self.config = self._load_config()
        
        self.setup_ui()
    
    def _load_config(self):
        """Load config từ file config.ini"""
        config = configparser.ConfigParser()
        config_path = os.path.join(SCRIPT_DIR, "config.ini")
        
        # Default values
        defaults = {
            'topic': '',
            'language': 'English',

            'gemini_url': 'https://gemini.google.com/app',
            'veo_url': 'https://labs.google/fx/tools/flow/project/75d49ef7-f93c-4654-b25e-21c8ba9bcc91',
            'profile_path': 'wo0vat7e.veo',
            'gemini_mode': 'Pro'
        }
        
        if os.path.exists(config_path):
            try:
                config.read(config_path, encoding='utf-8')
                result = {
                    'topic': config.get('Prompt', 'topic', fallback=defaults['topic']),
                    'language': config.get('Prompt', 'language', fallback=defaults['language']),

                    'gemini_url': config.get('URLs', 'gemini_url', fallback=defaults['gemini_url']),
                    'veo_url': config.get('URLs', 'veo_url', fallback=defaults['veo_url']),
                    'profile_path': config.get('Firefox', 'profile_path', fallback=defaults['profile_path']),
                    'gemini_mode': config.get('Browser', 'gemini_mode', fallback=defaults['gemini_mode'])
                }
                return result
            except:
                pass
        
        return defaults
        
    def _resolve_profile_path(self):
        """Resolve profile folder name to full path: BASE_DIR/tools/profiles/<folder_name>"""
        folder_name = self.firefox_profile.text().strip()
        return os.path.join(BASE_DIR, "tools", "profiles", folder_name)
    
    def setup_ui(self):
        """Setup UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("🎬 VEO VIDEO AUTOMATION SUITE")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        
        subtitle = QLabel("Workflow: Character → Voiceover → Video Prompts + Gemini + Create → Download → Review")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle)
        
        # Selenium status
        if not SELENIUM_AVAILABLE:
            warn = QLabel("⚠️ Selenium not installed! Browser automation will not work.")
            warn.setStyleSheet("color: red; font-weight: bold;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(warn)
        
        main_layout.addSpacing(10)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setMaximumHeight(280)
        main_layout.addWidget(self.tabs, stretch=0)
        
        self.create_tab1_voiceover()
        self.create_tab2_character()
        self.create_tab3_video()
        self.create_tab4_download()
        self.create_tab5_review()
        self.create_tab6_settings()
        
        # Console
        console_group = QGroupBox("📝 Console Output")
        console_layout = QVBoxLayout()
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))
        self.console.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        self.console.setMinimumHeight(300)
        console_layout.addWidget(self.console)
        
        console_group.setLayout(console_layout)
        main_layout.addWidget(console_group, stretch=1)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.stop_process)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(self.console.clear)
        control_layout.addWidget(clear_btn)
        
        control_layout.addStretch()
        
        self.status_label = QLabel("✅ Ready")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        control_layout.addWidget(self.status_label)
        
        main_layout.addLayout(control_layout)
        
        # Firefox Browser Control
        firefox_group = QGroupBox("🦊 Firefox Browser Control")
        firefox_layout = QHBoxLayout()
        
        # Headless Mode (left)
        self.headless_checkbox = QCheckBox("👻 Headless Mode (no GUI)")
        self.headless_checkbox.setChecked(False)  # Default: with GUI
        self.headless_checkbox.toggled.connect(self._on_headless_toggled)
        firefox_layout.addWidget(self.headless_checkbox)
        
        firefox_layout.addSpacing(20)
        
        # Hide Firefox (right)
        self.hide_firefox_checkbox = QCheckBox("🚫 Hide Firefox (push off-screen)")
        self.hide_firefox_checkbox.setChecked(True)  # Default: hide Firefox
        self.hide_firefox_checkbox.toggled.connect(self._on_hide_firefox_toggled)
        firefox_layout.addWidget(self.hide_firefox_checkbox)
        
        # Status note
        self.firefox_note_label = QLabel("(Headless mode: OFF)")
        self.firefox_note_label.setStyleSheet("color: gray; font-style: italic;")
        firefox_layout.addWidget(self.firefox_note_label)
        
        firefox_layout.addStretch()
        firefox_group.setLayout(firefox_layout)
        main_layout.addWidget(firefox_group)
    
    def _on_headless_toggled(self, checked):
        """Handle headless checkbox toggle"""
        if checked:
            # Headless ON → disable Hide Firefox checkbox
            self.hide_firefox_checkbox.setEnabled(False)
            self.firefox_note_label.setText("(Headless mode: ON)")
            self.firefox_note_label.setStyleSheet("color: orange; font-style: italic; font-weight: bold;")
        else:
            # Headless OFF → enable Hide Firefox checkbox
            self.hide_firefox_checkbox.setEnabled(True)
            self.firefox_note_label.setText("(Headless mode: OFF)")
            self.firefox_note_label.setStyleSheet("color: gray; font-style: italic;")
    
    def _on_hide_firefox_toggled(self, checked):
        """Handle hide firefox checkbox toggle - real-time update"""
        if self.current_worker and hasattr(self.current_worker, 'toggle_firefox_visibility'):
            # checked = hide, so show = not checked
            self.current_worker.toggle_firefox_visibility(not checked)
    
    # === Tab Creation Methods ===
    
    def create_tab1_voiceover(self):
        """Tab 1: Voiceover"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addWidget(QLabel("Tạo voiceover script từ topic + language (Settings)"))
        layout.addWidget(QLabel("💡 Bước 1: Prepare prompt → Bước 2: Run Gemini để generate"))
        layout.addStretch()
        
        btn1 = QPushButton("📝 Prepare Voiceover Prompt")
        btn1.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn1.setMinimumHeight(36)
        btn1.setStyleSheet("QPushButton { background-color: #2196F3; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #1976D2; }")
        btn1.clicked.connect(self.run_prepare_voiceover_prompt)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("🤖 Run Gemini → Get Voiceover Script")
        btn2.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn2.setMinimumHeight(36)
        btn2.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #388E3C; }")
        btn2.clicked.connect(self.run_voiceover_gemini)
        layout.addWidget(btn2)
        
        self.tabs.addTab(tab, "Tab 1 - Voiceover")
    
    def create_tab2_character(self):
        """Tab 2: Character Appearance"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addWidget(QLabel("Tạo character appearance description từ topic (Settings → Topic)"))
        layout.addWidget(QLabel("💡 Bước 1: Prepare prompt → Bước 2: Run Gemini để generate"))
        layout.addStretch()
        
        btn1 = QPushButton("📝 Prepare Character Prompt")
        btn1.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn1.setMinimumHeight(36)
        btn1.setStyleSheet("QPushButton { background-color: #2196F3; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #1976D2; }")
        btn1.clicked.connect(self.run_prepare_character_prompt)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("🤖 Run Gemini → Get Character Appearance")
        btn2.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn2.setMinimumHeight(36)
        btn2.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #388E3C; }")
        btn2.clicked.connect(self.run_character_gemini)
        layout.addWidget(btn2)
        
        self.tabs.addTab(tab, "Tab 2 - Character")
    
    def create_tab3_video(self):
        """Tab 3: Video (Create Prompts + Fill Gemini + Create Video)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addWidget(QLabel("Tạo video prompts → Fill Gemini → Auto create video trên Veo Flow"))
        layout.addWidget(QLabel("💡 Cấu hình paths và browser options tại tab Settings"))
        layout.addStretch()
        
        btn1 = QPushButton("▶️ Step 1: Generate Video Prompts")
        btn1.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn1.setMinimumHeight(36)
        btn1.setStyleSheet("QPushButton { background-color: #2196F3; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #1976D2; }")
        btn1.clicked.connect(self.run_create_prompts)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("▶️ Step 2: Run Auto Fill Gemini")
        btn2.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn2.setMinimumHeight(36)
        btn2.setStyleSheet("QPushButton { background-color: #FF9800; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #F57C00; }")
        btn2.clicked.connect(self.run_fill_gemini)
        layout.addWidget(btn2)
        
        btn3 = QPushButton("▶️ Step 3: Run Auto Create Videos")
        btn3.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn3.setMinimumHeight(36)
        btn3.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 4px; }"
                          "QPushButton:hover { background-color: #388E3C; }")
        btn3.clicked.connect(self.run_auto_create)
        layout.addWidget(btn3)
        
        self.tabs.addTab(tab, "Tab 3 - Video")
    
    def create_tab4_download(self):
        """Tab 4: Download Videos"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addWidget(QLabel("Download tất cả videos đã hoàn thành (Original 720p)"))
        layout.addWidget(QLabel("💾 Videos sẽ được save vào Downloads folder của Firefox."))
        layout.addWidget(QLabel("💡 Cấu hình browser options tại tab Settings"))
        layout.addStretch()
        
        run_btn = QPushButton("▶️ Download All Videos")
        run_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        run_btn.setMinimumHeight(40)
        run_btn.clicked.connect(self.run_download)
        layout.addWidget(run_btn)
        
        self.tabs.addTab(tab, "Tab 4 - Download")
    
    def create_tab5_review(self):
        """Tab 5: Review Videos"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addWidget(QLabel("Xem và chọn video tốt nhất cho mỗi scene (2 video/scene)"))
        layout.addWidget(QLabel("💡 Chọn folder chứa videos đã download, rồi review từng scene"))
        layout.addStretch()
        
        run_btn = QPushButton("🎬 Open Review Videos")
        run_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        run_btn.setMinimumHeight(40)
        run_btn.clicked.connect(self.open_review_dialog)
        layout.addWidget(run_btn)
        
        self.tabs.addTab(tab, "Tab 5 - Review")
    
    def create_tab6_settings(self):
        """Tab 6: Settings"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addWidget(QLabel("Configure prompt input, URLs và file paths cho automation workflow"))
        layout.addWidget(QLabel("💡 Click button bên dưới để mở Settings dialog"))
        layout.addStretch()
        
        open_settings_btn = QPushButton("⚙️ Open Settings")
        open_settings_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        open_settings_btn.setMinimumHeight(40)
        open_settings_btn.clicked.connect(self.open_settings_dialog)
        layout.addWidget(open_settings_btn)
        
        # Hidden fields for internal use
        self.gemini_url = QLineEdit(self.config['gemini_url'])
        self.veo_url = QLineEdit(self.config['veo_url'])
        self.firefox_profile = QLineEdit(self.config['profile_path'])
        self.topic = QLineEdit(self.config.get('topic', ''))
        self.language = QLineEdit(self.config.get('language', 'English'))

        self.template_path = QLineEdit(os.path.join(SCRIPT_DIR, "prompt_base", "prompt_3_video_scenes_story.txt"))
        self.character_path = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "2_character_appearance", "output_prompt_character_appearance.txt"))
        self.script_path = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "1_voiceover_60scenes", "output_prompt_voiceover_60scenes.txt"))
        self.output_path = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "3.1_prompt_video_60scenes_for_gemini"))
        self.gemini_output = QLineEdit(os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "3.2_prompt_video_60scenes_for_veo3", "prompt_video_60scenes.txt"))
        
        # Hidden checkboxes for browser wait options
        self.wait_for_enter = QCheckBox()
        self.download_wait_for_enter = QCheckBox()
        self.auto_restart_on_failure = QCheckBox()
        self.auto_restart_on_failure.setChecked(True)
        
        self.tabs.addTab(tab, "⚙️ Settings")
    
    # === Utility Methods ===
    
    def open_review_dialog(self):
        """Mở Review Videos Dialog"""
        default_path = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.dirname(default_path)
        
        folder = QFileDialog.getExistingDirectory(
            self, "Chọn folder chứa videos đã download", 
            default_path)
        
        if not folder:
            return
        
        dialog = ReviewVideosDialog(self, folder)
        
        if not dialog.scenes:
            QMessageBox.warning(self, "Warning", 
                f"Không tìm thấy video nào trong:\n{folder}\n\n"
                "Hỗ trợ: .mp4, .webm, .mkv, .avi, .mov")
            return
        
        self.log(f"🎬 Mở Review Videos: {len(dialog.scenes)} scenes từ {folder}")
        dialog.exec()
    
    def open_settings_dialog(self):
        """Mở Settings Dialog pop-up"""
        dialog = SettingsDialog(self, self.config)
        
        # Sync current values to dialog
        dialog.gemini_url.setText(self.gemini_url.text())
        dialog.veo_url.setText(self.veo_url.text())
        dialog.firefox_profile.setText(self.firefox_profile.text())
        dialog.topic.setText(self.topic.text())
        dialog.language.setText(self.language.text())

        dialog.template_path.setText(self.template_path.text())
        dialog.character_path.setText(self.character_path.text())
        dialog.script_path.setText(self.script_path.text())
        dialog.output_path.setText(self.output_path.text())
        dialog.gemini_output.setText(self.gemini_output.text())
        dialog.wait_for_enter_tab3.setChecked(self.wait_for_enter.isChecked())
        dialog.wait_for_enter_tab4.setChecked(self.download_wait_for_enter.isChecked())
        dialog.auto_restart_on_failure.setChecked(self.auto_restart_on_failure.isChecked())
        dialog.timeout_seconds.setValue(self._timeout_seconds)
        dialog.auto_restart_on_timeout.setChecked(self._auto_restart_on_timeout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Sync values back from dialog
            self.gemini_url.setText(dialog.gemini_url.text())
            self.veo_url.setText(dialog.veo_url.text())
            self.firefox_profile.setText(dialog.firefox_profile.text())
            self.topic.setText(dialog.topic.text())
            self.language.setText(dialog.language.text())

            self.template_path.setText(dialog.template_path.text())
            self.character_path.setText(dialog.character_path.text())
            self.script_path.setText(dialog.script_path.text())
            self.output_path.setText(dialog.output_path.text())
            self.gemini_output.setText(dialog.gemini_output.text())
            self.wait_for_enter.setChecked(dialog.wait_for_enter_tab3.isChecked())
            self.download_wait_for_enter.setChecked(dialog.wait_for_enter_tab4.isChecked())
            self.auto_restart_on_failure.setChecked(dialog.auto_restart_on_failure.isChecked())
            self._timeout_seconds = dialog.timeout_seconds.value()
            self._auto_restart_on_timeout = dialog.auto_restart_on_timeout.isChecked()
            
            # Reload config from file first
            self.config = self._load_config()
            
            # Then override gemini_mode with dialog selection (takes priority)
            mode_text = dialog.gemini_mode.currentText()
            self.config['gemini_mode'] = mode_text
            
            self.log(f"⚙️ Settings updated from dialog (Gemini Mode: {self.config.get('gemini_mode', 'Pro')})")
    
    def log(self, message):
        self.console.append(str(message))
        self.console.moveCursor(QTextCursor.MoveOperation.End)
    
    def set_running(self, running):
        self.is_running = running
        self.stop_btn.setEnabled(running)
        if running:
            self.status_label.setText("🔄 Running...")
            self.status_label.setStyleSheet("color: blue; font-weight: bold;")
        else:
            self.status_label.setText("✅ Ready")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
    
    def stop_process(self):
        if self.current_worker:
            self.log("\n⚠️ Stopping process...")
            self.current_worker.stop()
    
    def on_worker_output(self, message):
        self.log(message)
    
    def on_worker_finished(self, success, message):
        # Khi failed và browser vẫn mở → đưa Firefox ra foreground để debug
        browser_still_open = (
            not success 
            and self.current_worker 
            and hasattr(self.current_worker, 'driver') 
            and self.current_worker.driver
        )
        
        if browser_still_open:
            try:
                self.current_worker.toggle_firefox_visibility(True)
                self.log("🦊 Firefox đã được đưa ra foreground để debug")
                self.log("💡 Dùng checkbox 'Hide Firefox' để ẩn/hiện browser")
            except:
                pass
        
        self.set_running(False)
        
        # Giữ current_worker nếu browser vẫn mở (để toggle hide/show còn hoạt động)
        if not browser_still_open:
            self.current_worker = None
        
        if success:
            self.log(f"\n✅ {message}")
            QMessageBox.information(self, "Success", message)
        else:
            self.log(f"\n❌ {message}")
    
    # === Run Methods ===
    
    def run_prepare_character_prompt(self):
        """Prepare character appearance prompt from template + topic"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        topic = self.topic.text().strip()
        if not topic:
            QMessageBox.critical(self, "Error", 
                "Topic chưa được điền!\n\nVào Settings → Prompt Input → Topic để nhập.")
            return
        
        template_path = os.path.join(SCRIPT_DIR, "prompt_base", "prompt_1_character_appearance.txt")
        if not os.path.exists(template_path):
            QMessageBox.critical(self, "Error", f"Template file not found:\n{template_path}")
            return
        
        output_path = os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "2_character_appearance", "input_prompt_character_appearance.txt")
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Prepare Character Appearance Prompt")
        self.log("=" * 60 + "\n")
        
        self.current_worker = PrepareCharacterPromptWorker(
            topic, template_path, output_path
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_character_gemini(self):
        """Run prepared character prompt on Gemini"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        if not SELENIUM_AVAILABLE:
            QMessageBox.critical(self, "Error", "Selenium is not installed!")
            return
        
        input_path = os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "2_character_appearance", "input_prompt_character_appearance.txt")
        if not os.path.exists(input_path):
            QMessageBox.critical(self, "Error", 
                "Prepared prompt not found!\n\nHãy chạy 'Prepare Character Prompt' trước.")
            return
        
        output_path = self.character_path.text()
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Gemini → Character Appearance")
        self.log(f"⏱️ Timeout: {self._timeout_seconds}s")
        self.log("=" * 60 + "\n")
        
        self.current_worker = RunCharacterGeminiWorker(
            input_path, output_path,
            self._resolve_profile_path(),
            self.gemini_url.text(),
            self.hide_firefox_checkbox.isChecked(),
            self.headless_checkbox.isChecked(),
            self._timeout_seconds,
            True,  # auto_restart_on_timeout
            self.config.get('gemini_mode', 'Pro')
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_prepare_voiceover_prompt(self):
        """Prepare voiceover prompt from template + topic + language + scene range"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        topic = self.topic.text().strip()
        if not topic:
            QMessageBox.critical(self, "Error", 
                "Topic chưa được điền!\n\nVào Settings → Prompt Input → Topic để nhập.")
            return
        
        language = self.language.text().strip()
        if not language:
            QMessageBox.critical(self, "Error", 
                "Language chưa được điền!\n\nVào Settings → Prompt Input → Language để nhập.")
            return
        
        template_path = os.path.join(SCRIPT_DIR, "prompt_base", "prompt_2_voiceover.txt")
        if not os.path.exists(template_path):
            QMessageBox.critical(self, "Error", f"Template file not found:\n{template_path}")
            return
        
        output_path = os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "1_voiceover_60scenes", "input_prompt_voiceover_60scenes.txt")
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Prepare Voiceover Prompt")
        self.log("=" * 60 + "\n")
        
        self.current_worker = PrepareVoiceoverPromptWorker(
            topic, language,
            template_path, output_path
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_voiceover_gemini(self):
        """Run prepared voiceover prompt on Gemini"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        if not SELENIUM_AVAILABLE:
            QMessageBox.critical(self, "Error", "Selenium is not installed!")
            return
        
        input_path = os.path.join(SCRIPT_DIR, "..", "_output", "proceed_prompts", "1_voiceover_60scenes", "input_prompt_voiceover_60scenes.txt")
        if not os.path.exists(input_path):
            QMessageBox.critical(self, "Error", 
                "Prepared prompt not found!\n\nHãy chạy 'Prepare Voiceover Prompt' trước.")
            return
        
        output_path = self.script_path.text()
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Gemini → Voiceover Script")
        self.log(f"⏱️ Timeout: {self._timeout_seconds}s")
        self.log("=" * 60 + "\n")
        
        self.current_worker = RunVoiceoverGeminiWorker(
            input_path, output_path,
            self._resolve_profile_path(),
            self.gemini_url.text(),
            self.hide_firefox_checkbox.isChecked(),
            self.headless_checkbox.isChecked(),
            self._timeout_seconds,
            True,  # auto_restart_on_timeout
            self.config.get('gemini_mode', 'Pro')
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_create_prompts(self):
        """Step 1: Create video prompts"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        if not os.path.exists(self.template_path.text()):
            QMessageBox.critical(self, "Error", "Template file not found!")
            return
        if not os.path.exists(self.character_path.text()):
            QMessageBox.critical(self, "Error", "Character file not found!\n\nHãy chạy Tab 1 trước.")
            return
        if not os.path.exists(self.script_path.text()):
            QMessageBox.critical(self, "Error", "Script file not found!")
            return
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Create Video Prompts")
        self.log("=" * 60 + "\n")
        
        self.current_worker = CreatePromptsWorker(
            self.template_path.text(),
            self.character_path.text(),
            self.script_path.text(),
            self.output_path.text()
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_fill_gemini(self):
        """Step 2: Fill Gemini"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        if not SELENIUM_AVAILABLE:
            QMessageBox.critical(self, "Error", "Selenium is not installed!")
            return
        
        if not os.path.exists(self.output_path.text()):
            QMessageBox.critical(self, "Error", "Input prompts folder not found!")
            return
        
        # Show dialog to choose Start Over or Resume
        output_file = self.gemini_output.text()
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Fill Gemini Mode")
        msg.setText("Choose how to start:")
        msg.setInformativeText(
            "Start Over: Clear output file and start from Scene 1\n"
            "Resume: Continue from last completed scene"
        )
        
        start_over_btn = msg.addButton("Start Over", QMessageBox.ButtonRole.AcceptRole)
        resume_btn = msg.addButton("Resume", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        clicked = msg.clickedButton()
        
        if clicked == cancel_btn:
            return
        
        # Xóa trắng file output nếu chọn Start Over
        if clicked == start_over_btn:
            try:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('')  # Xóa trắng file
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Không thể xóa file output: {e}")
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Auto Fill Gemini")
        self.log(f"⏱️ Timeout: {self._timeout_seconds}s | Auto-restart on timeout: {'ON' if self._auto_restart_on_timeout else 'OFF'}")
        
        if clicked == start_over_btn:
            self.log(f"🗑️ Start Over: Đã xóa trắng file output")
        else:
            self.log(f"▶️ Resume: Sẽ tiếp tục từ scene cuối cùng")
        
        self.log("=" * 60 + "\n")
        
        self.current_worker = FillGeminiWorker(
            self.output_path.text(),
            self.gemini_output.text(),
            self._resolve_profile_path(),
            self.gemini_url.text(),
            self.hide_firefox_checkbox.isChecked(),
            self.headless_checkbox.isChecked(),
            self._timeout_seconds,
            self._auto_restart_on_timeout,
            self.config.get('gemini_mode', 'Pro')
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_auto_create(self):
        """Step 3: Auto create video"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        if not SELENIUM_AVAILABLE:
            QMessageBox.critical(self, "Error", "Selenium is not installed!")
            return
        
        if not os.path.exists(self.gemini_output.text()):
            QMessageBox.critical(self, "Error", "Gemini results file not found!")
            return
        
        reply = QMessageBox.question(
            self, "Confirm",
            "This may take hours. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Auto Create Videos")
        self.log(f"⏱️ Timeout: {self._timeout_seconds}s | Auto-restart on failure: {'ON' if self.auto_restart_on_failure.isChecked() else 'OFF'}")
        self.log("=" * 60 + "\n")
        
        self.current_worker = AutoCreateVideoWorker(
            self.gemini_output.text(),
            self.veo_url.text(),
            self._resolve_profile_path(),
            self.wait_for_enter.isChecked(),
            self.auto_restart_on_failure.isChecked(),
            self._timeout_seconds
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()
    
    def run_download(self):
        """Download videos"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "A process is already running!")
            return
        
        if not SELENIUM_AVAILABLE:
            QMessageBox.critical(self, "Error", "Selenium is not installed!")
            return
        
        reply = QMessageBox.question(
            self, "Confirm",
            "Download all videos from Veo Flow?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        
        self.console.clear()
        self.log("=" * 60)
        self.log("▶️ Running: Download All Videos")
        self.log("=" * 60 + "\n")
        
        self.current_worker = DownloadVideosWorker(
            self.veo_url.text(),
            self._resolve_profile_path(),
            self.download_wait_for_enter.isChecked()
        )
        self.current_worker.output_signal.connect(self.on_worker_output)
        self.current_worker.finished_signal.connect(self.on_worker_finished)
        
        self.set_running(True)
        self.current_worker.start()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = VeoGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
