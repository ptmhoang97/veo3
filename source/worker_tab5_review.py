"""
Review Videos Dialog - Dialog để review và chọn video tốt nhất cho mỗi scene
"""

import os
import re
import glob
import json

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QWidget,
    QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QColor, QBrush
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


class ReviewVideosDialog(QDialog):
    """Dialog để review và chọn video tốt nhất cho mỗi scene"""
    
    def __init__(self, parent, video_folder):
        super().__init__(parent)
        self.setWindowTitle("🎬 Review Videos - Chọn video tốt nhất cho mỗi scene")
        self.setModal(True)
        self.setMinimumSize(1400, 750)
        
        self.video_folder = video_folder
        self.scenes = []  # List of (video_a, video_b) tuples
        self.scene_names = []  # List of scene display names
        self.selections = {}  # scene_index -> 'a' or 'b'
        self.re_generates = set()  # scene indexes marked for re-generation
        self.regen_notes = {}  # scene_index -> note string
        self.current_scene_idx = -1
        
        # Media players
        self.player_a = QMediaPlayer()
        self.player_b = QMediaPlayer()
        self.audio_a = QAudioOutput()
        self.audio_b = QAudioOutput()
        self.player_a.setAudioOutput(self.audio_a)
        self.player_b.setAudioOutput(self.audio_b)
        
        self._load_videos()
        self._load_selections_from_json()
        self._setup_ui()
        
        if self.scenes:
            # Restore table status from loaded selections
            for idx in self.selections:
                self._update_table_status(idx)
            for idx in self.re_generates:
                self._update_table_regen(idx)
            self._show_scene(0)
    
    def _load_videos(self):
        """Load video files từ folder, parse Scene number từ filename và group theo scene"""
        folder_name = os.path.basename(self.video_folder)
        print(f"📂 Loading videos from folder: {folder_name}")
        video_extensions = ['*.mp4', '*.webm', '*.mkv', '*.avi', '*.mov']
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(glob.glob(os.path.join(self.video_folder, ext)))
        
        # Parse scene number từ filename: Scene_XX_visual_... hoặc scene_XX...
        scene_pattern = re.compile(r'[Ss]cene_?(\d+)', re.IGNORECASE)
        
        # Group videos theo scene number
        scene_groups = {}  # scene_number -> list of file paths
        unmatched = []  # Files không parse được scene number
        
        for f in video_files:
            basename = os.path.basename(f)
            match = scene_pattern.search(basename)
            if match:
                scene_num = int(match.group(1))
                if scene_num not in scene_groups:
                    scene_groups[scene_num] = []
                scene_groups[scene_num].append(f)
            else:
                unmatched.append(f)
        
        if scene_groups:
            # Có scene number trong filename → group theo scene, sort theo scene number
            for scene_num in sorted(scene_groups.keys()):
                files = scene_groups[scene_num]
                # Sort files trong cùng scene theo tên file
                files.sort(key=lambda f: os.path.basename(f).lower())
                
                video_a = files[0] if len(files) >= 1 else None
                video_b = files[1] if len(files) >= 2 else None
                if video_a:
                    self.scenes.append((video_a, video_b))
                    self.scene_names.append(f"Scene {scene_num}")
        else:
            # Fallback: không parse được scene number → ghép cặp theo thời gian sửa đổi
            video_files.sort(key=lambda f: os.path.getmtime(f))
            
            for i in range(0, len(video_files) - 1, 2):
                self.scenes.append((video_files[i], video_files[i + 1]))
                self.scene_names.append(f"Scene {i // 2 + 1}")
            
            if len(video_files) % 2 == 1:
                self.scenes.append((video_files[-1], None))
                self.scene_names.append(f"Scene {len(video_files) // 2 + 1}")
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header info
        self.header_label = QLabel(f"📂 Folder: {self.video_folder}")
        self.header_label.setFont(QFont("Consolas", 9))
        main_layout.addWidget(self.header_label)
        
        # Splitter: Scene list (left) | Video area (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # === LEFT PANEL: Scene Table ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        left_layout.addWidget(QLabel("📋 Danh sách Scenes:"))
        
        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(4)
        self.scene_table.setHorizontalHeaderLabels(["Scene", "Videos", "Status", "Re-gen"])
        self.scene_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.scene_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.scene_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.scene_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.scene_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.scene_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.scene_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scene_table.verticalHeader().setVisible(False)
        self.scene_table.setFont(QFont("Arial", 10))
        self.scene_table.cellClicked.connect(self._on_table_row_clicked)
        
        # Populate table
        self.scene_table.setRowCount(len(self.scenes))
        for i, (va, vb) in enumerate(self.scenes):
            # Scene name (dùng tên thực từ filename)
            display_name = self.scene_names[i] if i < len(self.scene_names) else f"Scene {i + 1}"
            name_item = QTableWidgetItem(display_name)
            name_item.setFont(QFont("Arial", 10))
            self.scene_table.setItem(i, 0, name_item)
            
            # Video count
            count = 2 if vb else 1
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scene_table.setItem(i, 1, count_item)
            
            # Status
            status_item = QTableWidgetItem("⬜ Chưa chọn")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scene_table.setItem(i, 2, status_item)
            
            # Re-gen
            regen_item = QTableWidgetItem("")
            regen_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scene_table.setItem(i, 3, regen_item)
        
        left_layout.addWidget(self.scene_table)
        splitter.addWidget(left_widget)
        
        # === RIGHT PANEL: Video Players ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        self.scene_label = QLabel("")
        self.scene_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.scene_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.scene_label)
        
        # Video area - 2 videos side by side
        video_layout = QHBoxLayout()
        
        # Video A
        video_a_group = QGroupBox("Video A")
        video_a_layout = QVBoxLayout()
        self.video_widget_a = QVideoWidget()
        self.video_widget_a.setMinimumSize(400, 300)
        self.player_a.setVideoOutput(self.video_widget_a)
        video_a_layout.addWidget(self.video_widget_a)
        
        ctrl_a_layout = QHBoxLayout()
        self.play_a_btn = QPushButton("▶️ Play")
        self.play_a_btn.clicked.connect(lambda: self._toggle_play(self.player_a, self.play_a_btn))
        ctrl_a_layout.addWidget(self.play_a_btn)
        self.file_a_label = QLabel("")
        self.file_a_label.setFont(QFont("Consolas", 8))
        ctrl_a_layout.addWidget(self.file_a_label, stretch=1)
        video_a_layout.addLayout(ctrl_a_layout)
        
        self.radio_a = QRadioButton("✅ Chọn Video A")
        self.radio_a.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.radio_a.clicked.connect(self._on_selection_changed)
        video_a_layout.addWidget(self.radio_a)
        video_a_group.setLayout(video_a_layout)
        video_layout.addWidget(video_a_group)
        
        # Video B
        video_b_group = QGroupBox("Video B")
        video_b_layout = QVBoxLayout()
        self.video_widget_b = QVideoWidget()
        self.video_widget_b.setMinimumSize(400, 300)
        self.player_b.setVideoOutput(self.video_widget_b)
        video_b_layout.addWidget(self.video_widget_b)
        
        ctrl_b_layout = QHBoxLayout()
        self.play_b_btn = QPushButton("▶️ Play")
        self.play_b_btn.clicked.connect(lambda: self._toggle_play(self.player_b, self.play_b_btn))
        ctrl_b_layout.addWidget(self.play_b_btn)
        self.file_b_label = QLabel("")
        self.file_b_label.setFont(QFont("Consolas", 8))
        ctrl_b_layout.addWidget(self.file_b_label, stretch=1)
        video_b_layout.addLayout(ctrl_b_layout)
        
        self.radio_b = QRadioButton("✅ Chọn Video B")
        self.radio_b.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.radio_b.clicked.connect(self._on_selection_changed)
        video_b_layout.addWidget(self.radio_b)
        video_b_group.setLayout(video_b_layout)
        video_layout.addWidget(video_b_group)
        
        # Button group for radio
        self.radio_group = QButtonGroup(self)
        self.radio_group.addButton(self.radio_a, 0)
        self.radio_group.addButton(self.radio_b, 1)
        
        right_layout.addLayout(video_layout, stretch=1)
        
        # Shared controls area
        shared_ctrl = QHBoxLayout()
        shared_ctrl.addStretch()
        
        self.play_both_btn = QPushButton("▶️ Play Both")
        self.play_both_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.play_both_btn.setMinimumHeight(38)
        self.play_both_btn.setMinimumWidth(140)
        self.play_both_btn.setStyleSheet("background-color: #1976D2; color: white; padding: 5px 15px;")
        self.play_both_btn.clicked.connect(self._play_both)
        shared_ctrl.addWidget(self.play_both_btn)
        
        shared_ctrl.addSpacing(30)
        
        self.regen_checkbox = QCheckBox("🔄 Re-generate")
        self.regen_checkbox.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.regen_checkbox.setStyleSheet("color: #D32F2F;")
        self.regen_checkbox.clicked.connect(self._on_regen_changed)
        shared_ctrl.addWidget(self.regen_checkbox)
        
        self.regen_note = QLineEdit()
        self.regen_note.setPlaceholderText("Lý do re-generate...")
        self.regen_note.setFont(QFont("Arial", 10))
        self.regen_note.setMinimumWidth(300)
        self.regen_note.setEnabled(False)
        self.regen_note.editingFinished.connect(self._on_regen_note_changed)
        shared_ctrl.addWidget(self.regen_note, stretch=1)
        
        shared_ctrl.addStretch()
        right_layout.addLayout(shared_ctrl)
        
        # Progress label
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setFont(QFont("Arial", 10))
        right_layout.addWidget(self.progress_label)
        
        splitter.addWidget(right_widget)
        
        # Set splitter sizes (30% left, 70% right)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter, stretch=1)
        
        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.copy_btn = QPushButton("📦 Copy to Delivery")
        self.copy_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.copy_btn.setMinimumHeight(45)
        self.copy_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 5px 20px;")
        self.copy_btn.clicked.connect(self._copy_to_delivery)
        btn_layout.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("💾 Save Selections")
        self.save_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.save_btn.setMinimumHeight(45)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 20px;")
        self.save_btn.clicked.connect(self._save_selections)
        btn_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("✖️ Close")
        close_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        close_btn.setMinimumHeight(45)
        close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(close_btn)
        
        main_layout.addLayout(btn_layout)
        
        if not self.scenes:
            self.scene_label.setText("⚠️ Không tìm thấy video nào trong folder!")
            self.save_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)
    
    def _on_table_row_clicked(self, row, col):
        """Khi click vào dòng trong table → nhảy tới scene đó"""
        self._save_current_selection()
        self._save_current_regen_note()
        self._show_scene(row)
    
    def _on_selection_changed(self):
        """Khi chọn radio A/B → cập nhật table status ngay và auto-save"""
        self._save_current_selection()
        self._update_table_status(self.current_scene_idx)
        self._update_progress()
        self._auto_save_json()
    
    def _update_table_status(self, idx):
        """Cập nhật cột Status trong table cho scene idx"""
        if idx < 0 or idx >= len(self.scenes):
            return
        
        status_item = self.scene_table.item(idx, 2)
        if idx in self.selections:
            choice = self.selections[idx].upper()
            status_item.setText(f"✅ Video {choice}")
            status_item.setForeground(QBrush(QColor("#2E7D32")))
        else:
            status_item.setText("⬜ Chưa chọn")
            status_item.setForeground(QBrush(QColor("#999999")))
    
    def _update_progress(self):
        """Cập nhật progress label"""
        selected_count = len(self.selections)
        regen_count = len(self.re_generates)
        text = f"Đã chọn: {selected_count}/{len(self.scenes)} scenes"
        if regen_count > 0:
            text += f"  |  🔄 Cần re-generate: {regen_count} scenes"
        self.progress_label.setText(text)
    
    def _show_scene(self, idx):
        """Hiển thị cặp video cho scene tại index"""
        if idx < 0 or idx >= len(self.scenes):
            return
        
        self.current_scene_idx = idx
        video_a, video_b = self.scenes[idx]
        
        # Stop players
        self.player_a.stop()
        self.player_b.stop()
        self.play_a_btn.setText("▶️ Play")
        self.play_b_btn.setText("▶️ Play")
        
        # Update labels
        display_name = self.scene_names[idx] if idx < len(self.scene_names) else f"Scene {idx + 1}"
        self.scene_label.setText(f"🎬 {display_name.upper()} ({idx + 1}/{len(self.scenes)})")
        
        # Highlight row in table
        self.scene_table.selectRow(idx)
        
        # Load video A
        self.player_a.setSource(QUrl.fromLocalFile(video_a))
        self.file_a_label.setText(os.path.basename(video_a))
        
        # Load video B
        if video_b:
            self.player_b.setSource(QUrl.fromLocalFile(video_b))
            self.file_b_label.setText(os.path.basename(video_b))
            self.radio_b.setEnabled(True)
        else:
            self.player_b.setSource(QUrl())
            self.file_b_label.setText("(không có)")
            self.radio_b.setEnabled(False)
        
        # Restore selection nếu đã chọn trước đó
        if idx in self.selections:
            if self.selections[idx] == 'a':
                self.radio_a.setChecked(True)
            else:
                self.radio_b.setChecked(True)
        else:
            self.radio_group.setExclusive(False)
            self.radio_a.setChecked(False)
            self.radio_b.setChecked(False)
            self.radio_group.setExclusive(True)
        
        # Restore regen checkbox and note
        self.regen_checkbox.setChecked(idx in self.re_generates)
        self.regen_note.setEnabled(idx in self.re_generates)
        self.regen_note.setText(self.regen_notes.get(idx, ""))
        
        self._update_progress()
    
    def _toggle_play(self, player, btn):
        """Toggle play/pause cho video player"""
        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
            btn.setText("▶️ Play")
        else:
            player.play()
            btn.setText("⏸️ Pause")
    
    def _play_both(self):
        """Play cả 2 video cùng lúc từ đầu"""
        self.player_a.setPosition(0)
        self.player_b.setPosition(0)
        self.player_a.play()
        self.play_a_btn.setText("⏸️ Pause")
        if self.current_scene_idx >= 0:
            video_a, video_b = self.scenes[self.current_scene_idx]
            if video_b:
                self.player_b.play()
                self.play_b_btn.setText("⏸️ Pause")
    
    def _on_regen_changed(self):
        """Khi tick/untick re-generate checkbox"""
        if self.current_scene_idx < 0:
            return
        if self.regen_checkbox.isChecked():
            self.re_generates.add(self.current_scene_idx)
            self.regen_note.setEnabled(True)
            self.regen_note.setFocus()
        else:
            self.re_generates.discard(self.current_scene_idx)
            self.regen_notes.pop(self.current_scene_idx, None)
            self.regen_note.setText("")
            self.regen_note.setEnabled(False)
        self._update_table_regen(self.current_scene_idx)
        self._update_progress()
        self._auto_save_json()
    
    def _on_regen_note_changed(self):
        """Khi note text thay đổi"""
        if self.current_scene_idx < 0:
            return
        text = self.regen_note.text().strip()
        if text:
            self.regen_notes[self.current_scene_idx] = text
        else:
            self.regen_notes.pop(self.current_scene_idx, None)
        self._auto_save_json()
    
    def _update_table_regen(self, idx):
        """Cập nhật cột Re-gen trong table cho scene idx"""
        if idx < 0 or idx >= len(self.scenes):
            return
        regen_item = self.scene_table.item(idx, 3)
        if idx in self.re_generates:
            regen_item.setText("🔄")
            regen_item.setForeground(QBrush(QColor("#D32F2F")))
        else:
            regen_item.setText("")
    
    def _save_current_selection(self):
        """Lưu selection hiện tại"""
        if self.current_scene_idx < 0:
            return
        if self.radio_a.isChecked():
            self.selections[self.current_scene_idx] = 'a'
        elif self.radio_b.isChecked():
            self.selections[self.current_scene_idx] = 'b'
    
    def _save_current_regen_note(self):
        """Lưu regen note text hiện tại"""
        if self.current_scene_idx < 0:
            return
        text = self.regen_note.text().strip()
        if text and self.current_scene_idx in self.re_generates:
            self.regen_notes[self.current_scene_idx] = text
        elif not text:
            self.regen_notes.pop(self.current_scene_idx, None)
    
    def _get_json_path(self):
        """Trả về path của file JSON lưu selections trong video folder"""
        return os.path.join(self.video_folder, "review_selections.json")
    
    def _load_selections_from_json(self):
        """Load selections từ JSON file nếu tồn tại"""
        json_path = self._get_json_path()
        if not os.path.exists(json_path):
            return
        
        try:
            with open(json_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # Handle both old format (dict with 'selections' key) and new format (array)
            if isinstance(data, dict) and 'selections' in data:
                data = data['selections']
            
            # Build lookup: scene_name -> scene_index
            name_to_idx = {}
            for idx, name in enumerate(self.scene_names):
                name_to_idx[name] = idx
            
            # Restore selections and re-generates from array
            loaded_count = 0
            for entry in data:
                scene_name = entry.get('scene')
                if scene_name not in name_to_idx:
                    continue
                
                scene_idx = name_to_idx[scene_name]
                
                # Determine selection by matching selected_file against actual loaded videos
                selected_file = entry.get('selected_file')
                if selected_file:
                    actual_a, actual_b = self.scenes[scene_idx]
                    actual_a_name = os.path.basename(actual_a) if actual_a else None
                    actual_b_name = os.path.basename(actual_b) if actual_b else None
                    
                    if selected_file == actual_a_name:
                        self.selections[scene_idx] = 'a'
                        loaded_count += 1
                    elif selected_file == actual_b_name:
                        self.selections[scene_idx] = 'b'
                        loaded_count += 1
                
                # Restore re-generate flag and note
                if entry.get('re_generate'):
                    self.re_generates.add(scene_idx)
                    note = entry.get('note', '')
                    if note:
                        self.regen_notes[scene_idx] = note
            
            if loaded_count > 0:
                self._loaded_count = loaded_count
        except Exception:
            pass
    
    def _save_selections(self):
        """Lưu selections vào JSON file trong video folder"""
        self._save_current_selection()
        
        if not self.selections and not self.re_generates:
            QMessageBox.warning(self, "Warning", "Chưa chọn video hoặc đánh dấu re-generate nào!")
            return
        
        # Build JSON data as simple array
        data = []
        
        for scene_idx, choice in sorted(self.selections.items()):
            video_a, video_b = self.scenes[scene_idx]
            selected_file = video_a if choice == 'a' else video_b
            scene_name = self.scene_names[scene_idx] if scene_idx < len(self.scene_names) else f"Scene {scene_idx + 1}"
            
            entry = {
                'scene': scene_name,
                'selected_file': os.path.basename(selected_file) if selected_file else None,
                'video_a': os.path.basename(video_a) if video_a else None,
                'video_b': os.path.basename(video_b) if video_b else None
            }
            
            # Add re-generate note if exists
            if scene_idx in self.re_generates:
                entry['re_generate'] = True
                if scene_idx in self.regen_notes:
                    entry['note'] = self.regen_notes[scene_idx]
            
            data.append(entry)
        
        # Save to JSON
        json_path = self._get_json_path()
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            regen_count = len(self.re_generates)
            msg = f"✅ Đã lưu {len(self.selections)}/{len(self.scenes)} selections vào:\n{json_path}"
            if regen_count > 0:
                msg += f"\n\n🔄 {regen_count} scenes được đánh dấu cần re-generate"
            QMessageBox.information(self, "Success", msg)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Lỗi lưu file: {e}")
    
    def _copy_to_delivery(self):
        """Copy selected videos to delivery folder (auto-created inside video folder)"""
        self._save_current_selection()
        self._auto_save_json()
        
        if not self.selections:
            QMessageBox.warning(self, "Warning", "Chưa chọn video nào!")
            return
        
        # Auto create delivery folder inside video folder
        delivery_folder = os.path.join(self.video_folder, "delivery")
        os.makedirs(delivery_folder, exist_ok=True)
        
        # Copy files
        import shutil
        copied_count = 0
        errors = []
        
        for scene_idx, choice in sorted(self.selections.items()):
            video_a, video_b = self.scenes[scene_idx]
            selected_file = video_a if choice == 'a' else video_b
            
            if not selected_file or not os.path.exists(selected_file):
                scene_name = self.scene_names[scene_idx] if scene_idx < len(self.scene_names) else f"Scene {scene_idx + 1}"
                errors.append(f"{scene_name}: File not found")
                continue
            
            filename = os.path.basename(selected_file)
            dst = os.path.join(delivery_folder, filename)
            
            try:
                shutil.copy2(selected_file, dst)
                copied_count += 1
            except Exception as e:
                errors.append(f"{filename}: {str(e)[:50]}")
        
        # Show result
        msg = f"🎉 Đã copy {copied_count}/{len(self.selections)} videos vào:\n{delivery_folder}"
        if errors:
            msg += f"\n\n⚠️ Errors ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more"
        
        QMessageBox.information(self, "Copy Complete", msg)
    
    def _on_close(self):
        """Auto-save và cleanup khi đóng dialog"""
        self._save_current_selection()
        self._save_current_regen_note()
        self._auto_save_json()
        self.player_a.stop()
        self.player_b.stop()
        self.reject()
    
    def _auto_save_json(self):
        """Tự động lưu JSON khi đóng (không hiện messagebox)"""
        if not self.selections and not self.re_generates:
            return
        
        data = []
        
        for scene_idx, choice in sorted(self.selections.items()):
            video_a, video_b = self.scenes[scene_idx]
            selected_file = video_a if choice == 'a' else video_b
            scene_name = self.scene_names[scene_idx] if scene_idx < len(self.scene_names) else f"Scene {scene_idx + 1}"
            
            entry = {
                'scene': scene_name,
                'selected_file': os.path.basename(selected_file) if selected_file else None,
                'video_a': os.path.basename(video_a) if video_a else None,
                'video_b': os.path.basename(video_b) if video_b else None
            }
            
            # Add re-generate note if exists
            if scene_idx in self.re_generates:
                entry['re_generate'] = True
                if scene_idx in self.regen_notes:
                    entry['note'] = self.regen_notes[scene_idx]
            
            data.append(entry)
        
        try:
            with open(self._get_json_path(), 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def closeEvent(self, event):
        self._save_current_selection()
        self._save_current_regen_note()
        self._auto_save_json()
        self.player_a.stop()
        self.player_b.stop()
        super().closeEvent(event)
