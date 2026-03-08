"""
Tab 3.1: Create Prompts Worker
Tạo file prompts từ template + character + script
- Scene 3: dùng prompt_5_video_scene3_intro.txt (avatar + story character + script)
- Scene 59: dùng prompt_6_video_scene59_outro.txt (avatar + story character + script)
- Scene 60: copy trực tiếp từ prompt_6_video_scene60_outro.txt
- Các scene còn lại: dùng prompt_3_video_scenes_story.txt (character + script)
"""

import os
import re
import traceback

from worker_base import WorkerThread, SCRIPT_DIR


class CreatePromptsWorker(WorkerThread):
    """Worker để tạo prompts"""
    
    def __init__(self, template_path, character_path, script_path, output_dir):
        super().__init__()
        self.template_path = template_path
        self.character_path = character_path
        self.script_path = script_path
        self.output_dir = output_dir
        
        # Special template paths
        prompt_base = os.path.join(SCRIPT_DIR, "prompt_base")
        self.avatar_path = os.path.join(prompt_base, "prompt_4_me_appearance.txt")
        self.intro_template_path = os.path.join(prompt_base, "prompt_5_video_scene3_intro.txt")
        self.outro59_template_path = os.path.join(prompt_base, "prompt_6_video_scene59_outro.txt")
        self.outro60_path = os.path.join(prompt_base, "prompt_6_video_scene60_outro.txt")
    
    def _read_file(self, path, label):
        """Helper to read a file and log"""
        name = os.path.basename(path)
        self.log(f"  📖 Reading {label}: {name}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def _generate_special_prompt(self, template_content, avatar_desc, character_desc, scene_text):
        """Generate prompt for scene 3 or 59 (intro/outro with avatar + story character)"""
        prompt = template_content
        prompt = prompt.replace("[Paste Your Appearance Description Here]", avatar_desc)
        prompt = prompt.replace("[Paste Narrator Appearance Description Here]", character_desc)
        prompt = prompt.replace("[Paste Script Scene Here]", scene_text)
        return prompt
    
    def run(self):
        try:
            self.log("🚀 Starting prompt generation...")
            self.log(f"📁 Output directory: {self.output_dir}\n")
            
            # Create output directory
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Read main template (for normal scenes)
            template_name = os.path.basename(self.template_path)
            self.log(f"📖 Reading base template: {template_name}")
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            self.log(f"✅ Template loaded: {template_name}\n")
            
            # Read character (story character - output from Tab 2)
            character_name = os.path.basename(self.character_path)
            self.log(f"👤 Reading character description: {character_name}")
            with open(self.character_path, 'r', encoding='utf-8') as f:
                character_desc = f.read().strip()
            self.log(f"✅ Character description loaded: {character_name}\n")
            
            # Read avatar (me appearance - for scene 3, 59)
            avatar_desc = None
            if os.path.exists(self.avatar_path):
                avatar_desc = self._read_file(self.avatar_path, "avatar appearance")
                self.log(f"✅ Avatar appearance loaded\n")
            
            # Read special templates
            intro_template = None
            if os.path.exists(self.intro_template_path):
                intro_template = self._read_file(self.intro_template_path, "intro template (scene 3)")
            
            outro59_template = None
            if os.path.exists(self.outro59_template_path):
                outro59_template = self._read_file(self.outro59_template_path, "outro template (scene 59)")
            
            outro60_content = None
            if os.path.exists(self.outro60_path):
                outro60_content = self._read_file(self.outro60_path, "outro content (scene 60)")
            
            self.log("")
            
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
            
            count = 0
            for scene_num in sorted(scenes.keys()):
                if self._stop_requested:
                    self.log("\n⚠️ Stopped by user")
                    break
                    
                scene_text = scenes[scene_num]
                
                # === SCENE 3: Intro (avatar morph vào story character) ===
                if scene_num == 3 and intro_template and avatar_desc:
                    prompt = self._generate_special_prompt(
                        intro_template, avatar_desc, character_desc, scene_text
                    )
                    self.log(f"  ✓ Scene {scene_num} saved (INTRO - special template)")
                
                # === SCENE 59: Outro (story character morph về avatar) ===
                elif scene_num == 59 and outro59_template and avatar_desc:
                    prompt = self._generate_special_prompt(
                        outro59_template, avatar_desc, character_desc, scene_text
                    )
                    self.log(f"  ✓ Scene {scene_num} saved (OUTRO - special template)")
                
                # === SCENE 60: Copy trực tiếp ===
                elif scene_num == 60 and outro60_content:
                    prompt = outro60_content
                    self.log(f"  ✓ Scene {scene_num} saved (OUTRO - direct copy)")
                
                # === NORMAL SCENES ===
                else:
                    prompt = template
                    prompt = prompt.replace("[Paste Character Description Here]", character_desc)
                    scene_with_label = f"SCENCE {scene_num}: {scene_text}"
                    prompt = prompt.replace("[Paste Script Scenes Here]", scene_with_label)
                    self.log(f"  ✓ Scene {scene_num} saved")
                
                # Save file
                file_path = os.path.join(self.output_dir, f"prompt_video_scene{scene_num}.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                count += 1
            
            self.log(f"\n✅ Successfully created {count} individual prompt files")
            self.log(f"📂 All files saved to: {self.output_dir}")
            
            if intro_template and avatar_desc:
                self.log("   🎬 Scene 3: Used intro template (avatar → story character)")
            if outro59_template and avatar_desc:
                self.log("   🎬 Scene 59: Used outro template (story character → avatar)")
            if outro60_content:
                self.log("   🎬 Scene 60: Direct copy from outro template")
            
            self.finished_signal.emit(True, "Prompts created successfully!")
            
        except Exception as e:
            self.log(f"\n❌ Error: {e}")
            self.log(traceback.format_exc())
            self.finished_signal.emit(False, str(e))
