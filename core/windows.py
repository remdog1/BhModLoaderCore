import os
import sys
import subprocess
import time
import ctypes
import winreg as reg
from pathlib import Path

def is_admin():
    """Check if the script is running with administrator privileges."""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()

def run_as_admin():
    """Run the script with administrator privileges."""
    if is_admin():
        print("Already running as administrator.")
    else:
        print("Requesting administrator privileges...")
        # Filter out --register flag when re-running
        filtered_args = [arg for arg in sys.argv if not arg.startswith('--')]
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(filtered_args), None, 1
        )

def get_app_path():
    """Get the application path."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_current_exe_path():
    """Get the current executable path."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        # For development, return the main.py path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'run.py'))


def register_as_latest():
    """
    Register the current instance as the latest mod loader version.
    This stores the executable path in HKEY_CURRENT_USER (no admin required).
    Always updates, even if another version was previously registered.
    """
    try:
        exe_path = get_current_exe_path()
        registry_key_path = r"Software\BrawlhallaModLoader"
        current_time = time.time()
        
        # Store in HKEY_CURRENT_USER (no admin required)
        with reg.CreateKey(reg.HKEY_CURRENT_USER, registry_key_path) as key:
            reg.SetValueEx(key, "LatestExecutable", 0, reg.REG_SZ, exe_path)
            reg.SetValueEx(key, "LastUpdated", 0, reg.REG_SZ, str(current_time))
        
        return exe_path
    except Exception as e:
        print(f"Error registering as latest: {e}")
        return None

def get_latest_exe_path():
    """
    Get the path to the latest registered mod loader executable.
    Returns the stored path, or current exe if not found.
    """
    try:
        registry_key_path = r"Software\BrawlhallaModLoader"
        with reg.OpenKey(reg.HKEY_CURRENT_USER, registry_key_path) as key:
            latest_path, _ = reg.QueryValueEx(key, "LatestExecutable")
            if os.path.exists(latest_path):
                return latest_path
    except (FileNotFoundError, OSError):
        pass
    
    # Fallback to current executable
    return get_current_exe_path()

def update_protocol_handlers():
    """
    Update protocol handlers to point to the latest registered mod loader.
    This tries to update without admin, but may require admin for HKEY_CLASSES_ROOT.
    AGGRESSIVELY clears old associations first.
    """
    try:
        latest_exe = get_latest_exe_path()
        if not latest_exe or not os.path.exists(latest_exe):
            print("Warning: Latest executable path not found, using current executable")
            latest_exe = get_current_exe_path()
        
        exe_dir = os.path.dirname(latest_exe)
        
        # Try to find icon
        icon_paths = [
            os.path.join(exe_dir, "file_icon.ico"),
            os.path.join(exe_dir, "ui", "ui_sources", "resources", "icons", "App.ico"),
            latest_exe  # Use exe for icon if no .ico found
        ]
        
        icon_path = latest_exe
        for path in icon_paths:
            if os.path.exists(path):
                icon_path = path
                break
        
        print(f"Updating protocol handlers to: {latest_exe}")
        
        # Try to update HKEY_CLASSES_ROOT (requires admin, but we'll try)
        try:
            # FIRST: Clear old associations aggressively
            print("Clearing old associations...")
            clear_existing_associations()
            
            # Update bmod:// protocol
            print("Updating bmod:// protocol...")
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"bmod") as key:
                reg.SetValue(key, None, reg.REG_SZ, "URL:Brawlhalla Mod")
                reg.SetValueEx(key, "URL Protocol", 0, reg.REG_SZ, "")
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"bmod\shell\open\command") as key:
                command = f'"{latest_exe}" "%1"'
                reg.SetValue(key, None, reg.REG_SZ, command)
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"bmod\DefaultIcon") as key:
                reg.SetValue(key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Update GameBanana protocol
            print("Updating gamebanana-brawlhalla protocol...")
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"gamebanana-brawlhalla") as key:
                reg.SetValue(key, None, reg.REG_SZ, "GameBanana Brawlhalla Mod")
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"gamebanana-brawlhalla\shell\open\command") as key:
                command = f'"{latest_exe}" "%1"'
                reg.SetValue(key, None, reg.REG_SZ, command)
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"gamebanana-brawlhalla\DefaultIcon") as key:
                reg.SetValue(key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Update .bmod file association - use standard program ID method
            print("Updating .bmod file association...")
            prog_id = "BrawlhallaModLoader.bmod"
            
            # Set .bmod extension to point to program ID
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, ".bmod") as key:
                reg.SetValue(key, None, reg.REG_SZ, prog_id)
            
            # Create/update program ID
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, prog_id) as key:
                reg.SetValue(key, None, reg.REG_SZ, "Brawlhalla Mod File")
            
            # Set icon for program ID
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, f"{prog_id}\\DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Set command for program ID
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, f"{prog_id}\\shell\\open\\command") as command_key:
                command = f'"{latest_exe}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)
            
            # Also set icon directly on .bmod extension (for compatibility)
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, ".bmod\\DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Also set command directly on .bmod extension (for compatibility)
            with reg.CreateKey(reg.HKEY_CLASSES_ROOT, ".bmod\\shell\\open\\command") as command_key:
                command = f'"{latest_exe}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)
            
            print(f"✓ Protocol handlers updated successfully!")
            print(f"  Executable: {latest_exe}")
            print(f"  Icon: {icon_path}")
            return True
        except PermissionError:
            # Admin required
            print("⚠ Admin privileges required to update protocol handlers.")
            print("  Please run the mod loader as Administrator to update file associations.")
            return False
        except Exception as e:
            print(f"Error updating protocol handlers: {e}")
            import traceback
            traceback.print_exc()
            return False
    except Exception as e:
        print(f"Error updating protocol handlers: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_latest_installation():
    """Find the latest Brawlhalla Mod Loader installation."""
    try:
        # Look in common installation directories
        search_paths = [
            Path.home() / "AppData" / "Local" / "Programs" / "Brawlhalla Mod Loader",
            Path("C:/Program Files/Brawlhalla Mod Loader"),
            Path("C:/Program Files (x86)/Brawlhalla Mod Loader"),
        ]
        
        for search_path in search_paths:
            if search_path.exists():
                exe_files = list(search_path.glob("Brawlhalla Mod Loader*.exe"))
                if exe_files:
                    # Return the most recent one
                    return max(exe_files, key=lambda x: x.stat().st_mtime)
        
        return None
    except Exception:
        return None

def register_associations():
    """
    Creates file and URL protocol associations in the Windows registry using robust methods.
    """
    if not is_admin():
        print("Requesting administrator privileges to register file associations.")
        run_as_admin()
        return

    try:
        # Use the latest registered executable path
        latest_exe = get_latest_exe_path()
        if latest_exe and os.path.exists(latest_exe):
            exe_path = latest_exe
            app_path = os.path.dirname(exe_path)
        else:
            # Fallback to finding installation
            latest_installation = find_latest_installation()
            if latest_installation:
                app_path = latest_installation.parent
                exe_path = str(latest_installation)
            else:
                app_path = get_app_path()
                exe_name = "Brawlhalla Mod Loader 2025 Beta.exe"
                exe_path = os.path.join(app_path, exe_name)
        
        # Multiple icon path fallbacks for robustness
        icon_paths = [
            os.path.join(app_path, "file_icon.ico"),
            os.path.join(app_path, "ui", "ui_sources", "resources", "icons", "App.ico"),
            exe_path  # Use executable as icon if no .ico found
        ]
        
        icon_path = None
        for path in icon_paths:
            if os.path.exists(path):
                icon_path = path
                break
        
        if not icon_path:
            icon_path = exe_path  # Fallback to executable
        
        print(f"Using executable: {exe_path}")
        print(f"Using icon: {icon_path}")
        
        # ROBUST METHOD 1: Clear existing associations first
        print("Clearing existing .bmod associations...")
        clear_existing_associations()
        
        # ROBUST METHOD 2: Copy icon to multiple locations
        print("Copying icon to multiple system locations...")
        copy_icon_to_system_locations(icon_path)
        
        # ROBUST METHOD 3: Multiple registration methods
        print("Registering file associations with multiple methods...")
        
        # Method 3a: Standard program ID registration
        register_standard_associations(exe_path, icon_path)
        
        # Method 3b: Direct extension association
        register_direct_extension_association(exe_path, icon_path)
        
        # Method 3c: Alternative program ID
        register_alternative_program_id(exe_path, icon_path)
        
        # Method 3d: Shell integration
        register_shell_integration(exe_path, icon_path)
        
        # ROBUST METHOD 4: Force icon cache refresh
        print("Forcing icon cache refresh...")
        refresh_icon_cache()
        
        print("ROBUST file and URL protocol associations created successfully!")
        print("If icons don't appear immediately, try restarting Windows Explorer or your computer.")

    except Exception as e:
        print(f"Error creating associations: {e}")
        import traceback
        print(f"Full error traceback: {traceback.format_exc()}")

def check_associations():
    """Check if the file associations are already registered."""
    try:
        prog_id = "BrawlhallaModLoader.bmod"
        with reg.OpenKey(reg.HKEY_CLASSES_ROOT, f"{prog_id}\\shell\\open\\command") as key:
            return True
    except FileNotFoundError:
        return False

def refresh_icon_cache():
    """Refresh the Windows icon cache by restarting explorer.exe"""
    try:
        # Kill explorer.exe
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], check=False, capture_output=True)
        time.sleep(2)
        # Restart explorer.exe
        subprocess.Popen(["explorer.exe"])
        print("Windows Explorer restarted to refresh icon cache.")
    except Exception as e:
        print(f"Error refreshing icon cache: {e}")

def clear_existing_associations():
    """Clear existing .bmod associations aggressively"""
    try:
        # Clear .bmod extension
        try:
            reg.DeleteKey(reg.HKEY_CLASSES_ROOT, ".bmod")
        except FileNotFoundError:
            pass
        
        # Clear program IDs
        program_ids = [
            "BrawlhallaModLoader.bmod",
            "BrawlhallaModLoader",
            "bmod",
            "BrawlhallaMod"
        ]
        
        for prog_id in program_ids:
            try:
                reg.DeleteKey(reg.HKEY_CLASSES_ROOT, prog_id)
            except FileNotFoundError:
                pass
        
        # Clear Applications entry
        try:
            reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"Applications\Brawlhalla Mod Loader 2025 Beta.exe")
        except FileNotFoundError:
            pass
        
        print("Cleared existing .bmod associations")
    except Exception as e:
        print(f"Error clearing associations: {e}")

def copy_icon_to_system_locations(icon_path):
    """Copy icon to multiple system locations for better visibility"""
    try:
        import shutil
        import os
        
        # Get system directories
        appdata = os.environ.get('APPDATA', '')
        localappdata = os.environ.get('LOCALAPPDATA', '')
        temp_dir = os.environ.get('TEMP', '')
        
        # Copy to multiple locations
        locations = [
            os.path.join(appdata, "BrawlhallaModLoader", "file_icon.ico"),
            os.path.join(localappdata, "BrawlhallaModLoader", "file_icon.ico"),
            os.path.join(temp_dir, "BrawlhallaModLoader_icon.ico"),
            os.path.join(os.path.dirname(icon_path), "file_icon.ico")
        ]
        
        for location in locations:
            try:
                os.makedirs(os.path.dirname(location), exist_ok=True)
                shutil.copy2(icon_path, location)
                print(f"Copied icon to: {location}")
            except Exception as e:
                print(f"Failed to copy icon to {location}: {e}")
                
    except Exception as e:
        print(f"Error copying icon to system locations: {e}")

def register_standard_associations(exe_path, icon_path):
    """Register standard program ID associations"""
    try:
        prog_id = "BrawlhallaModLoader.bmod"
        
        # HKEY_CLASSES_ROOT\.bmod -> BrawlhallaModLoader.bmod
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, ".bmod") as key:
            reg.SetValue(key, None, reg.REG_SZ, prog_id)

        # HKEY_CLASSES_ROOT\BrawlhallaModLoader.bmod
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, prog_id) as key:
            reg.SetValue(key, None, reg.REG_SZ, "Brawlhalla Mod File")
            
            # Set the icon
            with reg.CreateKey(key, "DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Set the open command
            with reg.CreateKey(key, r"shell\open\command") as command_key:
                command = f'"{exe_path}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)
            
            # Add "Open with Brawlhalla Mod Loader" context menu
            with reg.CreateKey(key, r"shell\openwith") as openwith_key:
                reg.SetValue(openwith_key, None, reg.REG_SZ, "Open with Brawlhalla Mod Loader")
                # Set icon for the context menu item
                with reg.CreateKey(openwith_key, "DefaultIcon") as openwith_icon_key:
                    reg.SetValue(openwith_icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
                with reg.CreateKey(openwith_key, "command") as openwith_command_key:
                    command = f'"{exe_path}" "%1"'
                    reg.SetValue(openwith_command_key, None, reg.REG_SZ, command)
        
        print("Standard associations registered")
    except Exception as e:
        print(f"Error registering standard associations: {e}")

def register_direct_extension_association(exe_path, icon_path):
    """Register direct extension association (alternative method)"""
    try:
        # Direct extension association
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, ".bmod") as key:
            reg.SetValue(key, None, reg.REG_SZ, "BrawlhallaModLoader")
            reg.SetValue(key, "Content Type", reg.REG_SZ, "application/x-brawlhalla-mod")
            reg.SetValue(key, "PerceivedType", reg.REG_SZ, "document")
            
            # Direct icon setting
            with reg.CreateKey(key, "DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Direct command setting
            with reg.CreateKey(key, r"shell\open\command") as command_key:
                command = f'"{exe_path}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)
        
        print("Direct extension association registered")
    except Exception as e:
        print(f"Error registering direct extension association: {e}")

def register_alternative_program_id(exe_path, icon_path):
    """Register alternative program ID for better compatibility"""
    try:
        alt_prog_id = "BrawlhallaMod"
        
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, alt_prog_id) as key:
            reg.SetValue(key, None, reg.REG_SZ, "Brawlhalla Mod File")
            
            # Set the icon
            with reg.CreateKey(key, "DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
            
            # Set the open command
            with reg.CreateKey(key, r"shell\open\command") as command_key:
                command = f'"{exe_path}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)
        
        print("Alternative program ID registered")
    except Exception as e:
        print(f"Error registering alternative program ID: {e}")

def register_shell_integration(exe_path, icon_path):
    """Register shell integration for Windows Explorer"""
    try:
        # bmod:// URL protocol association
        url_prog_id = "bmod"
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, url_prog_id) as key:
            reg.SetValue(key, None, reg.REG_SZ, "URL:Brawlhalla Mod")
            reg.SetValueEx(key, "URL Protocol", 0, reg.REG_SZ, "")
            
            # Set the icon
            with reg.CreateKey(key, "DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')

            # Set the open command
            with reg.CreateKey(key, r"shell\open\command") as command_key:
                command = f'"{exe_path}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)

        # Register GameBanana URL handling
        gamebanana_prog_id = "gamebanana-brawlhalla"
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, gamebanana_prog_id) as key:
            reg.SetValue(key, None, reg.REG_SZ, "GameBanana Brawlhalla Mod")
            
            # Set the icon
            with reg.CreateKey(key, "DefaultIcon") as icon_key:
                reg.SetValue(icon_key, None, reg.REG_SZ, f'"{icon_path}",0')

            # Set the open command
            with reg.CreateKey(key, r"shell\open\command") as command_key:
                command = f'"{exe_path}" "%1"'
                reg.SetValue(command_key, None, reg.REG_SZ, command)

        # Add to "Open With" list with proper icon
        with reg.CreateKey(reg.HKEY_CLASSES_ROOT, r"Applications\Brawlhalla Mod Loader 2025 Beta.exe") as app_key:
            reg.SetValue(app_key, None, reg.REG_SZ, "Brawlhalla Mod Loader 2025 Beta")
            # Set icon for the application in Open With list
            with reg.CreateKey(app_key, "DefaultIcon") as app_icon_key:
                reg.SetValue(app_icon_key, None, reg.REG_SZ, f'"{icon_path}",0')
            with reg.CreateKey(app_key, r"shell\open\command") as app_command_key:
                command = f'"{exe_path}" "%1"'
                reg.SetValue(app_command_key, None, reg.REG_SZ, command)
        
        print("Shell integration registered")
    except Exception as e:
        print(f"Error registering shell integration: {e}")

if __name__ == '__main__':
    if '--register' in sys.argv:
        register_associations()
