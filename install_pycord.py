"""
Script to install and configure py-cord 2.6.1 properly in the environment.

This script:
1. Uninstalls both discord.py and py-cord to avoid conflicts
2. Checks existing discord module in sys.path and removes it if necessary
3. Installs py-cord 2.6.1 using pip
4. Creates a site.py customization to ensure py-cord is prioritized
"""
import sys
import os
import subprocess
import shutil
import importlib.util
import importlib.metadata
import site

def uninstall_packages():
    """Uninstall discord.py and py-cord to start fresh"""
    print("Uninstalling discord.py and py-cord...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "discord.py", "discord-py", "py-cord"], 
                  capture_output=True, text=True)
    
def remove_discord_module():
    """Check for and remove any discord module from site-packages"""
    print("Checking for existing discord module...")
    for path in sys.path:
        if 'site-packages' in path:
            discord_path = os.path.join(path, 'discord')
            if os.path.exists(discord_path):
                print(f"Found discord module at {discord_path}")
                print("Removing existing discord module...")
                try:
                    shutil.rmtree(discord_path)
                    print("Successfully removed discord module")
                except Exception as e:
                    print(f"Error removing discord module: {e}")

def install_pycord():
    """Install py-cord 2.6.1"""
    print("Installing py-cord 2.6.1...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "py-cord==2.6.1"], 
                         capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise Exception("Failed to install py-cord")

def create_sitecustomize():
    """Create a sitecustomize.py file to ensure py-cord takes precedence"""
    print("Creating site customization for proper imports...")
    site_packages = site.getsitepackages()
    for site_path in site_packages:
        if 'site-packages' in site_path:
            sitecustomize_path = os.path.join(site_path, 'sitecustomize.py')
            with open(sitecustomize_path, 'w') as f:
                f.write("""
# Custom import handler to prioritize py-cord over discord.py
import sys
import os

def ensure_pycord_priority():
    \"\"\"Ensure py-cord takes priority in the import path\"\"\"
    for path in sys.path:
        if 'site-packages' in path:
            # Check for py-cord specific files to identify it
            pycord_marker = os.path.join(path, 'py_cord-2.6.1.dist-info')
            if os.path.exists(pycord_marker):
                # Move this path to the front of sys.path if it isn't already
                if sys.path[0] != path:
                    sys.path.remove(path)
                    sys.path.insert(0, path)
                    print(f"Prioritized {path} in sys.path for py-cord")
                    return True
    return False

# Run the prioritization
ensure_pycord_priority()
""")
            print(f"Created sitecustomize.py at {sitecustomize_path}")
            return
    print("Warning: Could not find site-packages directory")

def check_installation():
    """Check that py-cord was installed correctly"""
    print("\nChecking py-cord installation...")
    try:
        import discord
        version = getattr(discord, "__version__", "Unknown")
        print(f"Discord module version: {version}")
        print(f"Discord module path: {discord.__file__}")
        
        # Additional py-cord specific checks
        if hasattr(discord, "slash_command"):
            print("✓ Found discord.slash_command (py-cord feature)")
        else:
            print("✗ No discord.slash_command found")
            
        if hasattr(discord.ext, "bridge"):
            print("✓ Found discord.ext.bridge (py-cord feature)")
        else:
            print("✗ No discord.ext.bridge found")
            
    except ImportError as e:
        print(f"Error importing discord module: {e}")

def main():
    """Main installation process"""
    print("=" * 50)
    print("Py-cord 2.6.1 Installation Script")
    print("=" * 50)
    
    # Step 1: Uninstall existing packages
    uninstall_packages()
    
    # Step 2: Remove existing discord module
    remove_discord_module()
    
    # Step 3: Install py-cord 2.6.1
    install_pycord()
    
    # Step 4: Create site customization
    create_sitecustomize()
    
    # Step 5: Check installation
    check_installation()
    
    print("\nInstallation process complete. Please restart your Python interpreter.")
    
if __name__ == "__main__":
    main()