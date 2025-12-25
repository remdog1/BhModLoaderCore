"""
Asynchronous mod loading implementation for better UI responsiveness
"""
import asyncio
import threading
import time
import os
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import queue

from .mod import ModClass
from .basedispatch import SendNotification
from .notifications import NotificationType
from .variables import MODS_PATH, MOD_FILE_FORMAT, CheckExists


class AsyncModLoader:
    """
    Asynchronous mod loader that processes mods in chunks to prevent UI blocking
    """
    
    def __init__(self, mods_cache_path: str, max_workers: int = 2):
        self.mods_cache_path = mods_cache_path
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.progress_queue = queue.Queue()
        self.loading_mods = []
        self.completed_mods = []
        self.failed_mods = []
        
    def load_mods_async(self, progress_callback=None):
        """
        Load mods asynchronously with progress updates
        """
        def _load_mods():
            try:
                mods_hashes = []
                mod_files = []
                
                # Get list of mod files
                if MODS_PATH:
                    mods_path = MODS_PATH[0]
                    CheckExists(mods_path, True)
                    
                    for mod_file in os.listdir(mods_path):
                        mod_path = os.path.join(mods_path, mod_file)
                        if mod_file.endswith(f".{MOD_FILE_FORMAT}") and os.path.isfile(mod_path):
                            mod_files.append(mod_path)
                
                total_files = len(mod_files)
                processed_files = 0
                
                # Process mods in chunks
                chunk_size = max(1, total_files // 10)  # Process in 10 chunks
                
                for i in range(0, total_files, chunk_size):
                    chunk = mod_files[i:i + chunk_size]
                    
                    # Process chunk
                    for mod_path in chunk:
                        try:
                            SendNotification(NotificationType.LoadingMod, mod_path)
                            
                            # Create mod in background thread
                            future = self.executor.submit(self._load_single_mod, mod_path)
                            
                            # Wait for completion with timeout
                            try:
                                mod_class = future.result(timeout=30)  # 30 second timeout per mod
                                
                                if mod_class and mod_class.hash not in mods_hashes:
                                    mods_hashes.append(mod_class.hash)
                                    self.completed_mods.append(mod_class)
                                    
                                processed_files += 1
                                
                                # Update progress
                                if progress_callback:
                                    progress_callback(processed_files, total_files, mod_path)
                                    
                            except Exception as e:
                                print(f"Error loading mod {mod_path}: {e}")
                                self.failed_mods.append((mod_path, str(e)))
                                
                        except Exception as e:
                            print(f"Error processing mod file {mod_path}: {e}")
                            self.failed_mods.append((mod_path, str(e)))
                    
                    # Small delay to prevent UI blocking
                    time.sleep(0.1)
                
                return self.completed_mods
                
            except Exception as e:
                print(f"Error in async mod loading: {e}")
                return []
        
        # Run in background thread
        thread = threading.Thread(target=_load_mods, daemon=True)
        thread.start()
        return thread
    
    def _load_single_mod(self, mod_path: str) -> Optional[ModClass]:
        """
        Load a single mod file
        """
        try:
            mod_class = ModClass(modPath=mod_path, modsCachePath=self.mods_cache_path)
            return mod_class
        except Exception as e:
            print(f"Error loading mod {mod_path}: {e}")
            return None
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current loading progress
        """
        return {
            'loading': len(self.loading_mods),
            'completed': len(self.completed_mods),
            'failed': len(self.failed_mods),
            'total': len(self.loading_mods) + len(self.completed_mods) + len(self.failed_mods)
        }
    
    def cleanup(self):
        """
        Clean up resources
        """
        self.executor.shutdown(wait=True)


class ChunkedModProcessor:
    """
    Processes mod installation in chunks to prevent UI blocking
    """
    
    def __init__(self, mod_class: ModClass):
        self.mod_class = mod_class
        self.progress = 0
        self.total_steps = 0
        self.current_step = 0
        
    def install_chunked(self, chunk_size: int = 5):
        """
        Install mod in chunks with progress updates
        """
        try:
            # Calculate total steps
            self.total_steps = (
                len(self.mod_class.files) + 
                len(self.mod_class.swfs) + 
                sum(len(elements) for elements in self.mod_class.swfs.values())
            )
            
            # Process files in chunks
            self._process_files_chunked(chunk_size)
            
            # Process SWFs in chunks
            self._process_swfs_chunked(chunk_size)
            
            SendNotification(NotificationType.InstallingModFinished, self.mod_class.hash)
            return True
            
        except Exception as e:
            print(f"Error in chunked installation: {e}")
            return False
    
    def _process_files_chunked(self, chunk_size: int):
        """
        Process mod files in chunks
        """
        files = list(self.mod_class.files.items())
        
        for i in range(0, len(files), chunk_size):
            chunk = files[i:i + chunk_size]
            
            for el_id, file_name in chunk:
                try:
                    SendNotification(NotificationType.InstallingModFile, self.mod_class.hash, file_name)
                    
                    # Process file
                    file_element = self.mod_class.modSwf.getElementById(el_id)
                    if file_element:
                        file_element = file_element[0]
                        file_data = self.mod_class.modSwf.exportBinaryData(file_element)
                        
                        # Install file
                        from .gamefiles import GameFiles
                        GameFiles.installFile(file_name, file_data, self.mod_class.hash)
                    
                    self.current_step += 1
                    self._update_progress()
                    
                except Exception as e:
                    print(f"Error processing file {file_name}: {e}")
                
            # Small delay to prevent UI blocking
            time.sleep(0.05)
    
    def _process_swfs_chunked(self, chunk_size: int):
        """
        Process SWF files in chunks
        """
        swfs = list(self.mod_class.swfs.items())
        
        for i in range(0, len(swfs), chunk_size):
            chunk = swfs[i:i + chunk_size]
            
            for swf_name, swf_map in chunk:
                try:
                    SendNotification(NotificationType.InstallingModSwf, self.mod_class.hash, swf_name)
                    
                    # Process SWF
                    from .gamefiles import GetGameFileClass
                    game_file = GetGameFileClass(swf_name)
                    if game_file:
                        game_file.open()
                        self._process_swf_elements(game_file, swf_map, chunk_size)
                        game_file.addInstalledMod(self.mod_class.hash)
                        game_file.save()
                        game_file.close()
                    
                    self.current_step += 1
                    self._update_progress()
                    
                except Exception as e:
                    print(f"Error processing SWF {swf_name}: {e}")
                
            # Small delay to prevent UI blocking
            time.sleep(0.05)
    
    def _process_swf_elements(self, game_file, swf_map, chunk_size: int):
        """
        Process SWF elements in chunks
        """
        elements = []
        for category, category_elements in swf_map.items():
            for element in category_elements:
                elements.append((category, element))
        
        for i in range(0, len(elements), chunk_size):
            chunk = elements[i:i + chunk_size]
            
            for category, element in chunk:
                try:
                    if category == "scripts":
                        script_anchor, content = element
                        SendNotification(NotificationType.InstallingModSwfScript, self.mod_class.hash, script_anchor)
                        game_file.importScript(content, script_anchor, self.mod_class.hash)
                        
                    elif category == "sounds":
                        sound_anchor = element
                        SendNotification(NotificationType.InstallingModSwfSound, self.mod_class.hash, sound_anchor)
                        # Process sound...
                        
                    elif category == "sprites":
                        sprite = element
                        sprite_name = sprite if isinstance(sprite, str) else sprite["name"]
                        SendNotification(NotificationType.InstallingModSwfSprite, self.mod_class.hash, sprite_name)
                        # Process sprite...
                    
                    self.current_step += 1
                    self._update_progress()
                    
                except Exception as e:
                    print(f"Error processing element {element}: {e}")
            
            # Small delay to prevent UI blocking
            time.sleep(0.02)
    
    def _update_progress(self):
        """
        Update progress and send notification
        """
        if self.total_steps > 0:
            progress_percent = int((self.current_step / self.total_steps) * 100)
            SendNotification(NotificationType.Debug, f"Progress: {progress_percent}% ({self.current_step}/{self.total_steps})")
