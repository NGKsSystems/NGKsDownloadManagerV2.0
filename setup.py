"""
Setup script for NGK's Download Manager
Installs dependencies and sets up the application
"""

import subprocess
import sys
import os
from pathlib import Path

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    
    requirements = [
        "yt-dlp>=2023.12.30",
        "requests>=2.31.0",
        "huggingface-hub>=0.19.4",
        "Pillow>=10.0.0",
        "tqdm>=4.66.0",
        "beautifulsoup4>=4.12.0",
        "urllib3>=2.0.7"
    ]
    
    for requirement in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", requirement])
            print(f"✓ Installed {requirement}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install {requirement}: {e}")
            return False
    
    return True

def create_directories():
    """Create necessary directories"""
    print("Creating directories...")
    
    directories = [
        "downloads",
        "config",
        "logs",
        "cache"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✓ Created directory: {directory}")
        except Exception as e:
            print(f"✗ Failed to create directory {directory}: {e}")

def check_dependencies():
    """Check if all dependencies are available"""
    print("Checking dependencies...")
    
    dependencies = {
        "tkinter": "tkinter",
        "yt-dlp": "yt_dlp", 
        "requests": "requests",
        "huggingface_hub": "huggingface_hub",
        "PIL": "PIL",
        "tqdm": "tqdm",
        "bs4": "bs4"
    }
    
    missing = []
    
    for name, module in dependencies.items():
        try:
            __import__(module)
            print(f"✓ {name} is available")
        except ImportError:
            print(f"✗ {name} is missing")
            missing.append(name)
    
    return len(missing) == 0, missing

def main():
    """Main setup function"""
    print("=== NGK's Download Manager Setup ===")
    print()
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("✗ Python 3.8 or higher is required")
        return False
    
    print(f"✓ Python {sys.version} detected")
    
    # Install requirements
    if not install_requirements():
        print("\n✗ Failed to install some requirements")
        return False
    
    # Create directories
    create_directories()
    
    # Check dependencies
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        print(f"\n✗ Missing dependencies: {', '.join(missing)}")
        print("Please install them manually and run setup again")
        return False
    
    print("\n=== Setup Complete ===")
    print("✓ All dependencies installed")
    print("✓ Directories created")
    print("✓ Ready to run!")
    print("\nRun 'python main.py' to start the application")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Setup failed with error: {e}")
        sys.exit(1)