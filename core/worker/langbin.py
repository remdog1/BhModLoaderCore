import os
import io
import shutil
import json
from typing import Dict, List, Optional

from .variables import MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FOLDER
from .brawlhalla import BRAWLHALLA_FILES
from .basedispatch import SendNotification
from ..notifications import NotificationType
from ..utils.hash import HashFile

# Import DecodeLang functionality
import zlib
import re
import codecs
import time


class ByteReader:
    @staticmethod
    def ReadUint32BE(data: io.BytesIO) -> int:
        byte = data.read(4)
        return int.from_bytes(byte, byteorder="big")

    @staticmethod
    def ReadUint16BE(data: io.BytesIO) -> int:
        byte = data.read(2)
        return int.from_bytes(byte, byteorder="big")


class UTF8String:
    # ctor
    def __init__(self, length: int, string: str):
        self.length = length
        self.string = string

    # static class methods
    @classmethod
    def FromBytesIO(cls, data: io.BytesIO):
        length = ByteReader.ReadUint16BE(data)
        string = data.read(length).decode('utf-8')
        return cls(length, string)

    @classmethod
    def FromString(cls, string: str):
        return cls(len(string.encode('utf-8')), string)

    # public
    def WriteBytesIO(self, data: io.BytesIO) -> None:
        data.write(self.length.to_bytes(2, byteorder="big"))
        data.write(self.string.encode('utf-8'))


class Entry:
    # ctor
    def __init__(self, key: UTF8String, value: UTF8String):
        self.key: UTF8String = key
        self.value: UTF8String = value

    # public
    def WriteBytesIO(self, data: io.BytesIO) -> None:
        self.key.WriteBytesIO(data)
        self.value.WriteBytesIO(data)

    def SetValue(self, value: str) -> None:
        self.value = UTF8String.FromString(value)

    # static class methods
    @classmethod
    def FromBytesIO(cls, data: io.BytesIO):
        return cls(UTF8String.FromBytesIO(data), UTF8String.FromBytesIO(data))

    @classmethod
    def FromKeyValuePair(cls, key: str, value: str):
        return cls(UTF8String.FromString(key), UTF8String.FromString(value))


class LangFile:
    # ctor
    def __init__(self, filename: str):
        with open(filename, "rb") as fd:
            self.entries = []
            self.inflated_size = fd.read(4)
            self.zlibdata = fd.read()
            self.__ParseFile()

    # public
    def Save(self, filename: str) -> None:
        data: io.BytesIO = io.BytesIO()
        data.write(self.__WriteUint32BE(self.entry_count))
        for entry in self.entries:
            entry.WriteBytesIO(data)

        with open(filename, "wb") as fd:
            self.inflated_size = data.getbuffer().nbytes
            fd.write(self.inflated_size.to_bytes(4, byteorder="little"))
            self.zlibdata = zlib.compress(data.getbuffer())
            fd.write(self.zlibdata)

    def Dump(self, filename: str) -> None:
        with codecs.open(filename, "w", "utf-8") as fd:
            for entry in self.entries:
                fd.write(f"{entry.key.string}={entry.value.string}\n")

    def FromTextFile(self, filename: str) -> None:
        with codecs.open(filename, "r", "utf-8") as fd:
            data = fd.read()
            
            # Convert colon format to equals format for compatibility
            # This handles files that use "key: value" instead of "key=value"
            data = re.sub(r'^([^=\s:]+)\s*:\s*(.*?)(?=\n[^=\s:]|\n*$)', r'\1=\2', data, flags=re.MULTILINE | re.DOTALL)
            
            # Improved regex to capture more language key patterns
            # This handles both underscore patterns and other common patterns
            regex = re.compile(r"^([^=\s]+)\s*=\s*(.*?)(?=\n[^=\s]|\n*$)", re.MULTILINE | re.DOTALL)
            matches = regex.findall(data)
            SendNotification(NotificationType.Debug, f"Found {len(matches)} language entries in text file")
            
            for match in matches:
                key = match[0].strip()
                value = match[1].strip()
                if key and value:  # Only add non-empty entries
                    self[key] = value
                    SendNotification(NotificationType.Debug, f"Added language entry: {key} = {value}")

    # private
    def __ParseFile(self) -> None:
        self.data: io.BytesIO = io.BytesIO(zlib.decompress(self.zlibdata))
        self.entry_count: int = ByteReader.ReadUint32BE(self.data)

        while len(self.entries) < self.entry_count:
            self.entries.append(Entry.FromBytesIO(self.data))

    def __WriteUint32BE(self, number: int) -> bytes:
        return number.to_bytes(4, byteorder="big")

    # overrides
    def __setitem__(self, key: str, value: str) -> None:
        # Check if entry exists and update if it does
        for entry in self.entries:
            if entry.key.string == key:
                entry.SetValue(value)
                return
        
        # Add new entry if not found
        self.entries.append(Entry.FromKeyValuePair(key, value))
        self.entry_count += 1

    def __getitem__(self, key: str) -> Optional[str]:
        for entry in self.entries:
            if entry.key.string == key:
                return entry.value.string
        return None


class LangBinHandler:
    """
    Handles language.bin files for the Brawlhalla modloader
    """
    def __init__(self):
        self.language_original_paths = {}
        self.cache_path = os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FOLDER)
        self.mod_language_changes_path = os.path.join(MODLOADER_CACHE_PATH, "language_mod_tracking.json")
        
        self.mod_language_changes = {}  # Format: {mod_hash: {file_name: {key: new_value}}}
        
        for file_name, file_path in BRAWLHALLA_FILES.items():
            if file_name.startswith("language.") and file_name.endswith(".bin"):
                self.language_original_paths[file_name] = file_path
        
        self._backup_original_files()
        self._load_mod_changes()

    def _backup_original_files(self):
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)
            
        for file_name, file_path in self.language_original_paths.items():
            backup_file_path = os.path.join(self.cache_path, file_name)
            if not os.path.exists(backup_file_path):
                shutil.copy2(file_path, backup_file_path)

    def _get_target_file(self, original_filename: str) -> Optional[str]:
        # Extract just the filename from the path (handle cases like "languages/language.1.bin")
        if original_filename:
            # Get just the filename part (everything after the last slash)
            filename_only = original_filename.split('/')[-1] if '/' in original_filename else original_filename
            filename_only = filename_only.split('\\')[-1] if '\\' in filename_only else filename_only
            
            # Check for exact match with filename only
            if filename_only in self.language_original_paths:
                return filename_only
            
            # Handle .txt files by converting them to .bin and looking for the corresponding .bin file
            if filename_only.endswith('.txt'):
                bin_filename = filename_only.replace('.txt', '.bin')
                if bin_filename in self.language_original_paths:
                    return bin_filename
            
            # Handle generic language.bin
            if filename_only == "language.bin":
                for potential_file in sorted(self.language_original_paths.keys()):
                    if potential_file.startswith("language.") and potential_file.endswith(".bin"):
                        return potential_file
        
        return None

    def apply_mod_language_changes(self, mod_lang_file_path: str, mod_hash: str, original_filename: str = None) -> bool:
        try:
            target_file_name = self._get_target_file(original_filename)
            if not target_file_name:
                SendNotification(NotificationType.Error, f"Could not determine target language file for: {original_filename}")
                return False
            
            # Check if this is a .txt file or .bin file
            if original_filename and original_filename.endswith('.txt'):
                # Handle .txt file - create a temporary LangFile and load from text
                mod_lang_file = LangFile.__new__(LangFile)  # Create instance without calling __init__
                mod_lang_file.entries = []
                mod_lang_file.entry_count = 0
                mod_lang_file.inflated_size = b''
                mod_lang_file.zlibdata = b''
                
                # Load from text file
                mod_lang_file.FromTextFile(mod_lang_file_path)
            else:
                # Handle .bin file normally
                mod_lang_file = LangFile(mod_lang_file_path)
            
            if mod_hash not in self.mod_language_changes:
                self.mod_language_changes[mod_hash] = {}
            
            mod_changes = {entry.key.string: entry.value.string for entry in mod_lang_file.entries}
            self.mod_language_changes[mod_hash][target_file_name] = mod_changes
            
            self._rebuild_language_files()
            self._save_mod_changes()
            
            SendNotification(NotificationType.Success, f"Successfully applied language changes for mod {mod_hash}")
            return True
                
        except Exception as e:
            SendNotification(NotificationType.Error, f"Error applying language changes: {str(e)}")
            import traceback
            SendNotification(NotificationType.Debug, f"Full error traceback: {traceback.format_exc()}")
            return False

    def uninstall_mod_language_changes(self, mod_hash: str) -> bool:
        try:
            if mod_hash in self.mod_language_changes:
                del self.mod_language_changes[mod_hash]
            
            self._save_mod_changes()
            self._rebuild_language_files()
            
            SendNotification(NotificationType.Success, f"Successfully uninstalled language changes for mod {mod_hash}")
            return True

        except Exception as e:
            SendNotification(NotificationType.Error, f"Error uninstalling language changes: {str(e)}")
            return False

    def _rebuild_language_files(self):
        # 1. Aggregate all changes from all tracked mods.
        aggregated_changes = {}
        sorted_mod_hashes = sorted(self.mod_language_changes.keys())
        
        for mod_hash in sorted_mod_hashes:
            for file_name, key_values in self.mod_language_changes[mod_hash].items():
                if file_name not in aggregated_changes:
                    aggregated_changes[file_name] = {}
                aggregated_changes[file_name].update(key_values)

        # 2. Restore all original files to ensure a clean slate.
        self.restore_all_original_files()

        # 3. Apply the aggregated changes to the restored files.
        for file_name, key_values in aggregated_changes.items():
            target_game_file_path = self.language_original_paths.get(file_name)
            if target_game_file_path:
                try:
                    game_lang_file = LangFile(target_game_file_path)
                    
                    for key, value in key_values.items():
                        game_lang_file[key] = value
                    
                    game_lang_file.Save(target_game_file_path)
                except Exception as e:
                    SendNotification(NotificationType.Error, f"Error rebuilding {file_name}: {str(e)}")
                    import traceback
                    SendNotification(NotificationType.Debug, f"Rebuild error traceback: {traceback.format_exc()}")

    def restore_all_original_files(self):
        for lang_file, original_path in self.language_original_paths.items():
            backup_path = os.path.join(self.cache_path, lang_file)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, original_path)

    def _save_mod_changes(self):
        try:
            with open(self.mod_language_changes_path, "w", encoding="utf-8") as f:
                json.dump(self.mod_language_changes, f, indent=2)
        except Exception as e:
            SendNotification(NotificationType.Error, f"Error saving language change tracking: {str(e)}")
    
    def _load_mod_changes(self):
        try:
            if os.path.exists(self.mod_language_changes_path):
                with open(self.mod_language_changes_path, "r", encoding="utf-8") as f:
                    self.mod_language_changes = json.load(f)
        except Exception as e:
            self.mod_language_changes = {}


# Singleton instance
lang_bin_handler = LangBinHandler()