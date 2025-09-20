import os
import io
import shutil
import subprocess
import json
import requests
import zipfile
import time
import re
from typing import Dict, Optional, List, Tuple
from pathlib import Path

from .variables import MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FOLDER
from .brawlhalla import BRAWLHALLA_FILES, BRAWLHALLA_PATH
from .basedispatch import SendNotification
from ..notifications import NotificationType
from ..utils.hash import HashFile

class BnkHandler:
    def __init__(self):
        self.cache_dir = os.path.join(MODLOADER_CACHE_PATH, "bnk_cache")
        self.original_bnks: Dict[str, str] = {}  # filename -> original path
        self.mod_changes: Dict[str, Dict[str, Dict[str, bytes]]] = {}  # mod_hash -> {filename -> {wem_id -> wem_data}}
        # Add new tracking for original WEM files
        self.original_wems: Dict[str, Dict[int, bytes]] = {}  # filename -> {wem_id -> original_wem_data}
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        # Initialize wwiseutil tool path
        self.tools_dir = os.path.join(MODLOADER_CACHE_PATH, "tools")
        self.wwiser_path = os.path.join(self.tools_dir, "wwiseutil", "wwiseutil.exe")

        if not os.path.exists(self.wwiser_path):
            self.download_wwiser()
        
        if not os.path.exists(self.wwiser_path):
            self.download_wwiser()
            
    def download_wwiser(self) -> bool:
        """Download and set up the wwiser tool"""
        try:
            if not os.path.exists(self.tools_dir):
                os.makedirs(self.tools_dir)
                
            # Use wwiseutil instead of wwiser
            release_url = "https://api.github.com/repos/hpxro7/wwiseutil/releases/latest"
            response = requests.get(release_url)
            response.raise_for_status()
            
            release_data = response.json()
            download_url = None
            
            # Look for the command line version of wwiseutil
            for asset in release_data["assets"]:
                if asset["name"] == "wwiseutil.exe":
                    download_url = asset["browser_download_url"]
                    break
                    
            if not download_url:
                SendNotification(NotificationType.Error, "Could not find wwiseutil executable download URL")
                return False
                
            # Create wwiseutil directory
            wwiseutil_dir = os.path.join(self.tools_dir, "wwiseutil")
            if not os.path.exists(wwiseutil_dir):
                os.makedirs(wwiseutil_dir)
                
            # Download the executable directly
            self.wwiser_path = os.path.join(wwiseutil_dir, "wwiseutil.exe")
            response = requests.get(download_url)
            response.raise_for_status()
            
            with open(self.wwiser_path, "wb") as f:
                f.write(response.content)
                
            if not os.path.exists(self.wwiser_path):
                SendNotification(NotificationType.Error, "Failed to download wwiseutil executable")
                return False
                
            return True
            
        except Exception as e:
            SendNotification(NotificationType.Error, f"Error downloading wwiseutil tool: {str(e)}")
            return False
            
    def backup_original_file(self, filename: str) -> bool:
        """Backup original .bnk file if not already backed up"""
        if filename not in BRAWLHALLA_FILES or not filename.endswith('.bnk'):
            return False
            
        if filename not in self.original_bnks:
            original_path = BRAWLHALLA_FILES[filename]
            backup_path = os.path.join(self.cache_dir, f"original_{filename}")
            
            if not os.path.exists(backup_path):
                shutil.copy2(original_path, backup_path)
            
            self.original_bnks[filename] = backup_path
            
        return True
        
    def extract_wem_info(self, output: str) -> Dict[str, Tuple[int, int, int]]:
        """Extract WEM IDs and metadata from wwiseutil output"""
        wem_info = {}  # filename -> (id, offset, size)
        current_section = None
        header_found = False
        
        # Log the raw output for debugging
        with open(os.path.join(MODLOADER_CACHE_PATH, "logs", "wwiseutil_output.log"), "a", encoding="utf-8") as log:
            log.write("\n=== wwiseutil Output Analysis ===\n")
            log.write(output)
            log.write("\n=== End Output ===\n")
        
        lines = output.split('\n')
        for i, line in enumerate(lines):
            # Look for the WEM section header
            if 'Index  |Id' in line:
                current_section = 'wems'
                header_found = True
                continue
            
            if current_section == 'wems' and header_found:
                # Skip the separator line
                if line.startswith('----'):
                    continue
                    
                # Try to parse the line
                try:
                    if '|' in line:
                        parts = [p.strip() for p in line.strip().split('|')]
                        if len(parts) >= 4:
                            try:
                                index = int(parts[0])
                                wem_id = int(parts[1])
                                offset = int(parts[2])
                                size = int(parts[3])
                                
                                # Check if file exists with different formats
                                found_filename = None
                                possible_formats = [
                                    f"{index:03d}.wem",  # 3-digit format (001.wem)
                                    f"{index:02d}.wem",  # 2-digit format (01.wem)
                                    f"{index}.wem"       # No leading zeros (1.wem)
                                ]
                                
                                # Use the first format by default, will be updated when verifying files
                                wem_info[possible_formats[0]] = (wem_id, offset, size)
                                
                            except ValueError as ve:
                                with open(os.path.join(MODLOADER_CACHE_PATH, "logs", "wwiseutil_output.log"), "a", encoding="utf-8") as log:
                                    log.write(f"Failed to parse line {i}: {line}\nError: {str(ve)}\n")
                except Exception as e:
                    with open(os.path.join(MODLOADER_CACHE_PATH, "logs", "wwiseutil_output.log"), "a", encoding="utf-8") as log:
                        log.write(f"Error processing line {i}: {line}\nError: {str(e)}\n")
        
        return wem_info

    def verify_wem_files(self, directory: str, wem_info: Dict[str, Tuple[int, int, int]], log_file) -> Dict[int, str]:
        """
        Verify WEM files in directory and return mapping of WEM IDs to actual filenames
        Returns: Dict[wem_id -> actual_filename]
        """
        id_to_filename = {}
        files_in_dir = [f for f in os.listdir(directory) if f.endswith('.wem')]
        
        # Create reverse mapping of WEM IDs to expected filenames
        id_to_expected = {wem_id: filename for filename, (wem_id, _, _) in wem_info.items()}
        
        # First pass: Try to match files exactly as they are
        for filename in files_in_dir:
            try:
                # Try to get the index from the filename (remove .wem and convert to int)
                index = int(filename[:-4])  # Remove .wem extension
                
                # Find the WEM ID for this index
                for expected_file, (wem_id, _, _) in wem_info.items():
                    expected_index = int(expected_file[:-4])  # Remove .wem extension
                    if expected_index == index:
                        id_to_filename[wem_id] = filename
                        log_file.write(f"Matched file: {filename} -> WEM ID: {wem_id}\n")
                        break
                        
            except ValueError:
                continue  # Skip files that don't follow the numeric pattern
        
        # Verify we found all files
        missing_ids = set(id_to_expected.keys()) - set(id_to_filename.keys())
        if missing_ids:
            log_file.write(f"Warning: Could not find files for WEM IDs: {missing_ids}\n")
            
        return id_to_filename

    def find_matching_wem_file(self, directory: str, base_filename: str) -> Optional[str]:
        """Find a WEM file matching the given base filename, trying different formats"""
        # Try different possible formats (e.g., "001.wem", "01.wem", "1.wem")
        possible_names = [
            base_filename,  # Original format (e.g., "001.wem")
            f"{int(base_filename[:-4]):02d}.wem",  # 2-digit format (e.g., "01.wem")
            f"{int(base_filename[:-4])}.wem"  # No leading zeros (e.g., "1.wem")
        ]
        
        for name in possible_names:
            full_path = os.path.join(directory, name)
            if os.path.exists(full_path):
                return name
        return None

    def get_active_mods_for_file(self, target_file: str) -> Dict[str, Dict[str, bytes]]:
        """Get all active mods that have modified the target file
        Returns: Dict[mod_hash -> Dict[wem_id -> wem_data]]"""
        active_mods = {}
        for mod_hash, mod_changes in self.mod_changes.items():
            if target_file in mod_changes:
                active_mods[mod_hash] = mod_changes[target_file]
        return active_mods

    def compare_wem_files(self, file1_path: str, file2_path: str, chunk_size: int = 8192) -> bool:
        """
        Compare two WEM files content to determine if they are identical
        Returns: True if files are identical, False if different
        """
        if os.path.getsize(file1_path) != os.path.getsize(file2_path):
            return False
            
        with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)
                
                if chunk1 != chunk2:
                    return False
                    
                if not chunk1:  # EOF
                    break
                    
        return True

    def backup_original_wem(self, target_file: str, wem_id: int, wem_data: bytes) -> None:
        """Backup original WEM data if not already backed up"""
        if target_file not in self.original_wems:
            self.original_wems[target_file] = {}
        if wem_id not in self.original_wems[target_file]:
            self.original_wems[target_file][wem_id] = wem_data

    def apply_mod_changes(self, mod_file_path: str, mod_hash: str, target_file: str) -> bool:
        """Apply changes from a mod's .bnk file to the target game file"""
        try:
            # Create logs directory if it doesn't exist
            log_dir = os.path.join(MODLOADER_CACHE_PATH, "logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            # Open log file for this operation
            with open(os.path.join(log_dir, "bnk_operations.log"), "a", encoding="utf-8") as log:
                log.write(f"\n=== BNK Mod Installation {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                log.write(f"Mod File: {mod_file_path}\n")
                log.write(f"Target Game File: {BRAWLHALLA_FILES[target_file]}\n")
                log.write(f"Mod Hash: {mod_hash}\n\n")
                
                # Verify mod file exists and is readable
                if not os.path.exists(mod_file_path):
                    log.write(f"❌ Mod file does not exist: {mod_file_path}\n")
                    return False
                    
                try:
                    mod_size = os.path.getsize(mod_file_path)
                    log.write(f"Mod file size: {mod_size} bytes\n")
                except Exception as e:
                    log.write(f"❌ Cannot access mod file: {str(e)}\n")
                    return False
                
                # Ensure wwiseutil tool is available
                if not os.path.exists(self.wwiser_path):
                    if not self.download_wwiser():
                        log.write("❌ Failed to download wwiseutil tool\n")
                        return False
                        
                # Backup original first
                if not self.backup_original_file(target_file):
                    log.write("❌ Failed to backup original file\n")
                    return False
                    
                # Create unique temporary directories with sanitized names
                timestamp = int(time.time() * 1000)
                safe_target = "".join(c for c in target_file if c.isalnum() or c in "._-")
                mod_temp_dir = os.path.join(self.cache_dir, f"mod_{timestamp}_{safe_target}")
                game_temp_dir = os.path.join(self.cache_dir, f"game_{timestamp}_{safe_target}")
                
                log.write(f"Using temporary directories:\n")
                log.write(f"Mod temp dir: {mod_temp_dir}\n")
                log.write(f"Game temp dir: {game_temp_dir}\n\n")
                
                try:
                    # Clean up old directories if they exist
                    for dir_path in [mod_temp_dir, game_temp_dir]:
                        if os.path.exists(dir_path):
                            log.write(f"Cleaning up existing directory: {dir_path}\n")
                            shutil.rmtree(dir_path)
                        os.makedirs(dir_path)
                        log.write(f"Created directory: {dir_path}\n")
                    
                    # Extract and analyze mod file
                    log.write("\nExtracting and analyzing mod BNK file...\n")
                    extract_cmd = [
                        self.wwiser_path,
                        "-unpack",
                        "-filepath", mod_file_path,
                        "-output", mod_temp_dir,
                        "-verbose"
                    ]
                    log.write(f"Running command: {' '.join(extract_cmd)}\n")
                    
                    result = subprocess.run(
                        extract_cmd,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    # Log the complete output
                    log.write("Command output:\n")
                    log.write(result.stdout)
                    if result.stderr:
                        log.write("Command errors:\n")
                        log.write(result.stderr)
                    
                    if result.returncode != 0:
                        log.write(f"❌ Failed to extract mod BNK file:\n{result.stderr}\n")
                        SendNotification(NotificationType.Error, f"Failed to extract mod BNK file: {result.stderr}")
                        return False
                    
                    # Extract WEM info from output first
                    mod_wem_info = self.extract_wem_info(result.stdout)
                    log.write(f"\nFound {len(mod_wem_info)} WEM files in mod:\n")
                    
                    # Verify mod WEM files and get actual filenames
                    mod_id_to_filename = self.verify_wem_files(mod_temp_dir, mod_wem_info, log)
                    if not mod_id_to_filename:
                        log.write("❌ Failed to verify mod WEM files\n")
                        return False
                    
                    # Extract and analyze game file
                    log.write("\nExtracting and analyzing game BNK file...\n")
                    result = subprocess.run(
                        [
                            self.wwiser_path,
                            "-unpack",
                            "-filepath", BRAWLHALLA_FILES[target_file],
                            "-output", game_temp_dir,
                            "-verbose"
                        ],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    if result.returncode != 0:
                        log.write(f"❌ Failed to extract game BNK file:\n{result.stderr}\n")
                        SendNotification(NotificationType.Error, f"Failed to extract game BNK file: {result.stderr}")
                        return False
                    
                    # Extract WEM info from game file
                    game_wem_info = self.extract_wem_info(result.stdout)
                    log.write(f"Found {len(game_wem_info)} WEM files in game:\n")
                    
                    # Verify game WEM files and get actual filenames
                    game_id_to_filename = self.verify_wem_files(game_temp_dir, game_wem_info, log)
                    if not game_id_to_filename:
                        log.write("❌ Failed to verify game WEM files\n")
                        return False
                    
                    # Get all active mods for this file
                    active_mods = self.get_active_mods_for_file(target_file)
                    log.write(f"\nFound {len(active_mods)} active mods for {target_file}\n")
                    
                    # Create a mapping of WEM IDs that are already modified by other mods
                    protected_wem_ids = set()
                    for other_mod_hash, other_mod_changes in active_mods.items():
                        if other_mod_hash != mod_hash:  # Don't include current mod
                            protected_wem_ids.update(int(wem_id) for wem_id in other_mod_changes.keys())
                            log.write(f"Protected WEM IDs from mod {other_mod_hash}: {protected_wem_ids}\n")
                    
                    # Before replacing WEM files, read and backup the original content
                    for wem_id, game_filename in game_id_to_filename.items():
                        game_wem_path = os.path.join(game_temp_dir, game_filename)
                        if os.path.exists(game_wem_path):
                            with open(game_wem_path, 'rb') as f:
                                original_wem_data = f.read()
                                self.backup_original_wem(target_file, wem_id, original_wem_data)
                    
                    # Replace WEM files based on IDs, preserving other mods' changes
                    log.write("\nAnalyzing and replacing WEM files...\n")
                    replaced_count = 0
                    skipped_identical = 0
                    
                    for wem_id, mod_filename in mod_id_to_filename.items():
                        if wem_id in game_id_to_filename:
                            # Check if this WEM ID is protected by another mod
                            if wem_id in protected_wem_ids:
                                log.write(f"⚠️ Skipping WEM ID {wem_id} ({mod_filename}) - Protected by another mod\n")
                                continue
                                
                            game_filename = game_id_to_filename[wem_id]
                            mod_wem_path = os.path.join(mod_temp_dir, mod_filename)
                            game_wem_path = os.path.join(game_temp_dir, game_filename)
                            
                            # Verify both files exist before comparing
                            if not os.path.exists(mod_wem_path):
                                log.write(f"❌ Missing mod WEM file: {mod_filename}\n")
                                continue
                                
                            if not os.path.exists(game_wem_path):
                                log.write(f"❌ Missing game WEM file: {game_filename}\n")
                                continue

                            # Compare file contents before replacing
                            if self.compare_wem_files(mod_wem_path, game_wem_path):
                                log.write(f"ℹ️ Skipping WEM ID {wem_id} - Files are identical\n")
                                skipped_identical += 1
                                continue
                            
                            # Read the WEM data for tracking
                            with open(mod_wem_path, "rb") as f:
                                wem_data = f.read()
                                if mod_hash not in self.mod_changes:
                                    self.mod_changes[mod_hash] = {}
                                if target_file not in self.mod_changes[mod_hash]:
                                    self.mod_changes[mod_hash][target_file] = {}
                                self.mod_changes[mod_hash][target_file][str(wem_id)] = wem_data
                            
                            # Copy the WEM file
                            shutil.copy2(mod_wem_path, game_wem_path)
                            replaced_count += 1
                            
                            # Log detailed replacement info
                            mod_size = os.path.getsize(mod_wem_path)
                            game_size = os.path.getsize(game_wem_path)
                            log.write(f"✓ Replaced WEM ID {wem_id}:\n")
                            log.write(f"  - From: {game_filename} ({game_size} bytes)\n")
                            log.write(f"  - To: {mod_filename} ({mod_size} bytes)\n")
                        else:
                            log.write(f"⚠️ Skipped WEM ID {wem_id} ({mod_filename}) - No matching ID in game file\n")
                    
                    log.write(f"\nReplacement Summary:\n")
                    log.write(f"- Total WEM files: {len(game_wem_info)}\n")
                    log.write(f"- Files replaced: {replaced_count}\n")
                    log.write(f"- Files skipped (identical): {skipped_identical}\n")
                    log.write(f"- Files protected by other mods: {len(protected_wem_ids)}\n")
                    
                    # Restore protected WEM files from other mods
                    log.write("\nRestoring protected WEM files from other mods...\n")
                    for other_mod_hash, other_mod_changes in active_mods.items():
                        if other_mod_hash != mod_hash:
                            for wem_id_str, wem_data in other_mod_changes.items():
                                wem_id = int(wem_id_str)
                                if wem_id in game_id_to_filename:
                                    game_filename = game_id_to_filename[wem_id]
                                    game_wem_path = os.path.join(game_temp_dir, game_filename)
                                    
                                    # Write the protected WEM data
                                    with open(game_wem_path, "wb") as f:
                                        f.write(wem_data)
                                    log.write(f"✓ Restored protected WEM ID {wem_id} from mod {other_mod_hash}\n")
                    
                    log.write(f"\nReplaced {replaced_count} out of {len(game_wem_info)} WEM files\n")
                    
                    # Rebuild the game BNK file
                    log.write("\nRebuilding game BNK file...\n")
                    temp_output = os.path.join(self.cache_dir, f"temp_{target_file}")
                    
                    result = subprocess.run(
                        [
                            self.wwiser_path,
                            "-replace",
                            "-filepath", BRAWLHALLA_FILES[target_file],
                            "-target", game_temp_dir,
                            "-output", temp_output,
                            "-verbose"
                        ],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    if result.returncode != 0:
                        log.write(f"❌ Failed to rebuild game BNK file:\n{result.stderr}\n")
                        SendNotification(NotificationType.Error, f"Failed to rebuild game BNK file: {result.stderr}")
                        return False
                    
                    # Verify the rebuilt BNK
                    verify_result = subprocess.run(
                        [
                            self.wwiser_path,
                            "-unpack",
                            "-filepath", temp_output,
                            "-output", os.path.join(self.cache_dir, "verify_temp"),
                            "-verbose"
                        ],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    if verify_result.returncode == 0:
                        rebuilt_wem_info = self.extract_wem_info(verify_result.stdout)
                        log.write("\nVerification of rebuilt BNK file:\n")
                        log.write(f"Found {len(rebuilt_wem_info)} WEM files\n")
                        
                        # Only verify the number of WEM files matches
                        if len(rebuilt_wem_info) == len(game_wem_info):
                            shutil.copy2(temp_output, BRAWLHALLA_FILES[target_file])
                            os.utime(BRAWLHALLA_FILES[target_file], None)  # Update modification time to force recognition of changes
                            log.write("✓ Successfully replaced game BNK file\n")
                            
                            # Compare file sizes
                            original_size = os.path.getsize(self.original_bnks[target_file])
                            new_size = os.path.getsize(BRAWLHALLA_FILES[target_file])
                            log.write(f"\nFile size comparison:\n")
                            log.write(f"Original: {original_size} bytes\n")
                            log.write(f"Modified: {new_size} bytes\n")
                            
                            # Update modification time
                            os.utime(BRAWLHALLA_FILES[target_file], None)
                            log.write("✓ Successfully applied mod changes\n")
                            if self.get_active_mods_for_file(target_file):
                                shutil.copy2(BRAWLHALLA_FILES[target_file], self.original_bnks[target_file])
                                log.write("✓ Updated original backup to new BNK file for preservation of remaining mod changes\n")
                            return True
                        else:
                            log.write("❌ Verification failed - wrong number of WEM files\n")
                            
                    # Restore from backup if verification fails
                    log.write("Restoring from backup...\n")
                    if target_file in self.original_bnks:
                        shutil.copy2(self.original_bnks[target_file], BRAWLHALLA_FILES[target_file])
                        log.write("✓ Restored from backup\n")
                    SendNotification(NotificationType.Warning, "BNK file verification failed - restored original file")
                    return False
                    
                finally:
                    # Clean up temporary directories
                    for dir_path in [mod_temp_dir, game_temp_dir]:
                        if os.path.exists(dir_path):
                            try:
                                shutil.rmtree(dir_path)
                            except Exception as e:
                                log.write(f"Warning: Failed to clean up temporary directory {dir_path}: {str(e)}\n")
                    
        except Exception as e:
            error_msg = f"Error applying BNK changes: {str(e)}"
            with open(os.path.join(log_dir, "bnk_operations.log"), "a", encoding="utf-8") as log:
                log.write(f"\n❌ {error_msg}\n")
            SendNotification(NotificationType.Error, error_msg)
            return False
            
    def uninstall_mod_changes(self, mod_hash: str) -> bool:
        try:
            log_dir = os.path.join(MODLOADER_CACHE_PATH, "logs")
            with open(os.path.join(log_dir, "bnk_operations.log"), "a", encoding="utf-8") as log:
                log.write(f"\n=== BNK Mod Uninstallation {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                log.write(f"Mod Hash: {mod_hash}\n")
                
                if mod_hash not in self.mod_changes:
                    log.write("No BNK changes found for this mod\n")
                    return True
                
                # Process each modified file
                for target_file, wem_changes in self.mod_changes[mod_hash].items():
                    log.write(f"\nProcessing {target_file}...\n")
                    log.write(f"Number of WEM changes to revert: {len(wem_changes)}\n")
                    
                    # Get all active mods for this file
                    active_mods = self.get_active_mods_for_file(target_file)
                    active_mods.pop(mod_hash, None)  # Remove current mod from active mods
                    log.write(f"Found {len(active_mods)} other active mods for {target_file}\n")
                    
                    # Debug: Check which mods are active and their changes
                    for other_hash, other_changes in active_mods.items():
                        log.write(f"Mod {other_hash} has {len(other_changes)} WEM changes\n")
                    
                    # Create temporary directories for extraction and modification
                    timestamp = int(time.time() * 1000)
                    safe_target = "".join(c for c in target_file if c.isalnum() or c in "._-")
                    temp_dir = os.path.join(self.cache_dir, f"uninstall_{timestamp}_{safe_target}")
                    debug_dir = os.path.join(self.cache_dir, f"debug_{timestamp}_{safe_target}")
                    
                    try:
                        # Create temp directories
                        os.makedirs(temp_dir)
                        os.makedirs(debug_dir)
                        log.write(f"Created temporary directory: {temp_dir}\n")
                        log.write(f"Created debug directory: {debug_dir}\n")
                        
                        # First, extract the current game BNK to get the structure
                        log.write("\nExtracting current game BNK file...\n")
                        result = subprocess.run(
                            [
                                self.wwiser_path,
                                "-unpack",
                                "-filepath", BRAWLHALLA_FILES[target_file],
                                "-output", temp_dir,
                                "-verbose"
                            ],
                            capture_output=True,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        
                        if result.returncode != 0:
                            log.write(f"❌ Failed to extract game BNK file\n")
                            continue
                            
                        # Get current WEM files info and verify
                        current_wem_info = self.extract_wem_info(result.stdout)
                        current_id_to_filename = self.verify_wem_files(temp_dir, current_wem_info, log)
                        
                        # Create a map of which mod owns each WEM file
                        wem_ownership = {}  # wem_id -> (mod_hash, wem_data)
                        for other_hash, other_changes in active_mods.items():
                            for wem_id_str, wem_data in other_changes.items():
                                wem_id = int(wem_id_str)
                                wem_ownership[wem_id] = (other_hash, wem_data)
                                log.write(f"WEM ID {wem_id} is owned by mod {other_hash}\n")
                        
                        # Track changes made during uninstallation
                        changes_made = False
                        restored_count = 0
                        preserved_count = 0
                        
                        # First handle files owned by other mods
                        log.write("\nPreserving WEM files owned by other mods...\n")
                        for wem_id, (owner_hash, wem_data) in wem_ownership.items():
                            if wem_id in current_id_to_filename:
                                wem_filename = current_id_to_filename[wem_id]
                                wem_path = os.path.join(temp_dir, wem_filename)
                                debug_path = os.path.join(debug_dir, f"{wem_filename}.preserved")
                                
                                # Debug: Save the WEM data to debug directory
                                with open(debug_path, 'wb') as f:
                                    f.write(wem_data)
                                    
                                # Write the WEM data from the owning mod
                                with open(wem_path, 'wb') as f:
                                    f.write(wem_data)
                                    
                                # Verify data was written correctly
                                with open(wem_path, 'rb') as f:
                                    written_data = f.read()
                                    if written_data == wem_data:
                                        log.write(f"✓ Verified WEM ID {wem_id} ({wem_filename}) data matches expected ({len(wem_data)} bytes)\n")
                                    else:
                                        log.write(f"❌ Data mismatch for WEM ID {wem_id} ({wem_filename})! Expected {len(wem_data)} bytes, got {len(written_data)} bytes\n")
                                        
                                log.write(f"✓ Preserved WEM ID {wem_id} ({wem_filename}) from mod {owner_hash}\n")
                                preserved_count += 1
                                changes_made = True
                        
                        # Then process each WEM file that needs to be reverted
                        log.write("\nRestoring original WEM files...\n")
                        for wem_id_str in wem_changes.keys():
                            wem_id = int(wem_id_str)
                            # Skip if this WEM is owned by another mod
                            if wem_id in wem_ownership:
                                log.write(f"Skipping WEM ID {wem_id} - Owned by another mod\n")
                                continue
                                
                            if wem_id in current_id_to_filename:
                                wem_filename = current_id_to_filename[wem_id]
                                wem_path = os.path.join(temp_dir, wem_filename)
                                debug_path = os.path.join(debug_dir, f"{wem_filename}.original")
                                
                                # No other mod owns this WEM, restore original
                                if target_file in self.original_wems and wem_id in self.original_wems[target_file]:
                                    original_data = self.original_wems[target_file][wem_id]
                                    
                                    # Debug: Save the original WEM data
                                    with open(debug_path, 'wb') as f:
                                        f.write(original_data)
                                    
                                    with open(wem_path, 'wb') as f:
                                        f.write(original_data)
                                        
                                    # Verify data was written correctly
                                    with open(wem_path, 'rb') as f:
                                        written_data = f.read()
                                        if written_data == original_data:
                                            log.write(f"✓ Verified original data for WEM ID {wem_id} ({wem_filename}) matches expected ({len(original_data)} bytes)\n")
                                        else:
                                            log.write(f"❌ Data mismatch for original WEM ID {wem_id} ({wem_filename})! Expected {len(original_data)} bytes, got {len(written_data)} bytes\n")
                                    
                                    restored_count += 1
                                    changes_made = True
                                    log.write(f"✓ Restored original WEM ID {wem_id} ({wem_filename})\n")
                                else:
                                    log.write(f"⚠️ No original backup found for WEM ID {wem_id}\n")
                        
                        # Save a copy of the directory for debugging
                        log.write("\nSaving directory contents for verification...\n")
                        for filename in os.listdir(temp_dir):
                            src_path = os.path.join(temp_dir, filename)
                            dst_path = os.path.join(debug_dir, filename)
                            if os.path.isfile(src_path):
                                try:
                                    shutil.copy2(src_path, dst_path)
                                    log.write(f"Copied {filename} to debug directory\n")
                                except Exception as e:
                                    log.write(f"Failed to copy {filename}: {str(e)}\n")
                        
                        if changes_made:
                            log.write(f"\nRebuilding {target_file}:\n")
                            log.write(f"- Restored {restored_count} original WEM files\n")
                            log.write(f"- Preserved {preserved_count} WEM files from other mods\n")
                            
                            # Create a temporary output file
                            temp_output = os.path.join(self.cache_dir, f"temp_uninstall_{target_file}")
                            
                            # Use the current game BNK as the base
                            rebuild_cmd = [
                                self.wwiser_path,
                                "-replace",
                                "-filepath", BRAWLHALLA_FILES[target_file],  # Use current game file as base
                                "-target", temp_dir,
                                "-output", temp_output,
                                "-verbose"
                            ]
                            
                            log.write(f"Running rebuild command: {' '.join(rebuild_cmd)}\n")
                            result = subprocess.run(rebuild_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                            
                            if result.returncode == 0:
                                # Before verifying, let's check the WEM files in the rebuilt BNK
                                verify_temp_dir = os.path.join(self.cache_dir, "verify_temp")
                                if os.path.exists(verify_temp_dir):
                                    shutil.rmtree(verify_temp_dir)
                                os.makedirs(verify_temp_dir)
                                
                                verify_result = subprocess.run(
                                    [
                                        self.wwiser_path,
                                        "-unpack",
                                        "-filepath", temp_output,
                                        "-output", verify_temp_dir,
                                        "-verbose"
                                    ],
                                    capture_output=True,
                                    text=True
                                )
                                
                                if verify_result.returncode == 0:
                                    rebuilt_wem_info = self.extract_wem_info(verify_result.stdout)
                                    log.write(f"\nVerification Results:\n")
                                    log.write(f"- Original WEM count: {len(current_wem_info)}\n")
                                    log.write(f"- Rebuilt WEM count: {len(rebuilt_wem_info)}\n")
                                    
                                    # Copy the rebuilt BNK for debugging
                                    debug_bnk = os.path.join(debug_dir, f"rebuilt_{target_file}")
                                    try:
                                        shutil.copy2(temp_output, debug_bnk)
                                        log.write(f"Saved rebuilt BNK to {debug_bnk} for debugging\n")
                                    except Exception as e:
                                        log.write(f"Failed to save rebuilt BNK: {str(e)}\n")
                                    
                                    # Also save an unmodified copy of the game file for comparison
                                    game_bnk = os.path.join(debug_dir, f"game_{target_file}")
                                    try:
                                        shutil.copy2(BRAWLHALLA_FILES[target_file], game_bnk)
                                        log.write(f"Saved game BNK to {game_bnk} for comparison\n")
                                    except Exception as e:
                                        log.write(f"Failed to save game BNK: {str(e)}\n")
                                    
                                    # Verify content of WEM files in rebuilt BNK
                                    verification_passed = True
                                    for wem_id_str in wem_changes.keys():
                                        wem_id = int(wem_id_str)
                                        if wem_id in current_id_to_filename:
                                            wem_filename = current_id_to_filename[wem_id]
                                            rebuilt_wem_path = os.path.join(verify_temp_dir, wem_filename)
                                            
                                            if not os.path.exists(rebuilt_wem_path):
                                                log.write(f"❌ Missing WEM file in rebuilt BNK: {wem_filename}\n")
                                                verification_passed = False
                                                continue
                                            
                                            # Verify content based on whether it should be original or from another mod
                                            if wem_id in wem_ownership:
                                                owner_hash, expected_data = wem_ownership[wem_id]
                                                with open(rebuilt_wem_path, 'rb') as f:
                                                    actual_data = f.read()
                                                if len(actual_data) != len(expected_data):
                                                    log.write(f"❌ WEM file {wem_filename} size mismatch: expected {len(expected_data)} bytes, got {len(actual_data)} bytes\n")
                                                    verification_passed = False
                                            else:
                                                # Should be original content
                                                if wem_id in self.original_wems[target_file]:
                                                    with open(rebuilt_wem_path, 'rb') as f:
                                                        actual_data = f.read()
                                                    if len(actual_data) != len(self.original_wems[target_file][wem_id]):
                                                        log.write(f"❌ WEM file {wem_filename} size mismatch: expected {len(self.original_wems[target_file][wem_id])} bytes, got {len(actual_data)} bytes\n")
                                                        verification_passed = False
                                    
                                    # Apply changes if verification passes
                                    if verification_passed and len(rebuilt_wem_info) == len(current_wem_info):
                                        shutil.copy2(temp_output, BRAWLHALLA_FILES[target_file])
                                        os.utime(BRAWLHALLA_FILES[target_file], None)  # Update modification time
                                        log.write(f"✓ Successfully updated {target_file}\n")
                                        if self.get_active_mods_for_file(target_file):
                                            shutil.copy2(BRAWLHALLA_FILES[target_file], self.original_bnks[target_file])
                                            log.write("✓ Updated original backup to new BNK file for preservation of remaining mod changes\n")
                                    else:
                                        log.write("❌ Verification failed - content mismatch or wrong WEM count\n")
                                        log.write(f"Debug directory with all files: {debug_dir}\n")
                                        log.write("Keeping current game file state due to verification failure\n")
                                else:
                                    log.write("❌ Verification failed - extraction error\n")
                            else:
                                log.write(f"❌ Failed to rebuild BNK file\n")
                        else:
                            log.write("ℹ️ No changes needed for this file\n")
                            
                    finally:
                        # Keep debug directory for analysis but clean up other temps
                        log.write(f"Debug directory available at: {debug_dir}\n")
                        if os.path.exists(temp_dir):
                            try:
                                shutil.rmtree(temp_dir)
                                log.write(f"✓ Cleaned up temporary directory: {temp_dir}\n")
                            except Exception as e:
                                log.write(f"Warning: Failed to clean up {temp_dir}: {str(e)}\n")
                        if 'temp_output' in locals() and os.path.exists(temp_output):
                            try:
                                os.remove(temp_output)
                                log.write(f"✓ Cleaned up temporary output file\n")
                            except Exception as e:
                                log.write(f"Warning: Failed to clean up temp output: {str(e)}\n")
                
                # Remove this mod's changes from tracking
                del self.mod_changes[mod_hash]
                log.write("\n✅ BNK uninstallation completed successfully\n")
                
            return True
            
        except Exception as e:
            error_msg = f"Error uninstalling BNK changes: {str(e)}"
            with open(os.path.join(log_dir, "bnk_operations.log"), "a", encoding="utf-8") as log:
                log.write(f"\n❌ {error_msg}\n")
            SendNotification(NotificationType.Error, error_msg)
            return False
            
    def restore_all_original_files(self) -> bool:
        """Restore all original .bnk files"""
        try:
            for filename, backup_path in self.original_bnks.items():
                if filename in BRAWLHALLA_FILES:
                    # Restore file and update timestamp
                    shutil.copy2(backup_path, BRAWLHALLA_FILES[filename])
                    current_time = time.time()
                    os.utime(BRAWLHALLA_FILES[filename], (current_time, current_time))
            return True
        except Exception as e:
            SendNotification(NotificationType.Error, f"Error restoring original BNK files: {str(e)}")
            return False

# Global instance
bnk_handler = BnkHandler() 
