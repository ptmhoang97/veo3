"""
Tab 1: Create Prompts Worker
Tạo file prompts từ template + character + script
"""

import os
import re
import traceback

from worker_base import WorkerThread


class CreatePromptsWorker(WorkerThread):
    """Worker để tạo prompts"""
    
    def __init__(self, template_path, character_path, script_path, output_dir):
        super().__init__()
        self.template_path = template_path
        self.character_path = character_path
        self.script_path = script_path
        self.output_dir = output_dir
    
    def run(self):
        try:
            self.log("🚀 Starting prompt generation...")
            self.log(f"📁 Output directory: {self.output_dir}\n")
            
            # Create output directory
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Read template
            template_name = os.path.basename(self.template_path)
            self.log(f"📖 Reading base template: {template_name}")
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            self.log(f"✅ Template loaded: {template_name}\n")
            
            # Read character
            character_name = os.path.basename(self.character_path)
            self.log(f"👤 Reading character description: {character_name}")
            with open(self.character_path, 'r', encoding='utf-8') as f:
                character_desc = f.read()
            self.log(f"✅ Character description loaded: {character_name}\n")
            
            # Read and parse script
            script_name = os.path.basename(self.script_path)
            self.log(f"📝 Reading script scenes: {script_name}")
            with open(self.script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Parse scenes (support both "Scene" and "SCENCE" spelling)
            pattern = r'S[Cc][Ee][Nn][Cc]?[Ee]\s+(\d+):\s*(.+?)(?=(?:S[Cc][Ee][Nn][Cc]?[Ee]\s+\d+:|$))'
            matches = re.findall(pattern, script_content, re.DOTALL)
            scenes = {int(num): text.strip() for num, text in matches}
            self.log(f"✅ Found {len(scenes)} scenes\n")
            
            # Generate prompts
            self.log("⚙️ Generating individual prompt files...")
            
            for scene_num in sorted(scenes.keys()):
                if self._stop_requested:
                    self.log("\n⚠️ Stopped by user")
                    break
                    
                scene_text = scenes[scene_num]
                
                # Generate prompt
                prompt = template
                prompt = prompt.replace("[Paste Character Description Here]", character_desc.strip())
                scene_with_label = f"SCENCE {scene_num}: {scene_text.strip()}"
                prompt = prompt.replace("[Paste Script Scenes Here]", scene_with_label)
                
                # Save file
                file_path = os.path.join(self.output_dir, f"prompt_video_scene{scene_num}.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                self.log(f"  ✓ Scene {scene_num} saved")
            
            self.log(f"\n✅ Successfully created {len(scenes)} individual prompt files")
            self.log(f"📂 All files saved to: {self.output_dir}")
            
            self.finished_signal.emit(True, "Prompts created successfully!")
            
        except Exception as e:
            self.log(f"\n❌ Error: {e}")
            self.log(traceback.format_exc())
            self.finished_signal.emit(False, str(e))
