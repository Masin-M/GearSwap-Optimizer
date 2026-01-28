"""
FFXI Gear Set Optimizer - Standalone Launcher

This script launches the FastAPI server and opens the browser automatically.
Designed to be compiled with PyInstaller into a standalone executable.

Features:
- System tray icon with right-click menu
- Auto-opens browser on startup
- Clean shutdown from tray
"""

import os
import sys
import time
import threading
import webbrowser

# Server state
server_instance = None
shutdown_event = threading.Event()

# Detect if we're running without a console (windowed mode)
def is_windowed_mode():
    """Check if running without a console window."""
    if sys.platform == 'win32':
        try:
            # Try to get console window handle
            import ctypes
            return ctypes.windll.kernel32.GetConsoleWindow() == 0
        except:
            pass
    # Also check if stdout is None (another sign of no console)
    return sys.stdout is None or sys.stderr is None

# Set up logging/output handling
def setup_output():
    """Configure output handling based on whether we have a console."""
    if is_windowed_mode() or sys.stdout is None:
        # Redirect stdout/stderr to devnull to prevent crashes
        # Use UTF-8 encoding with error replacement to handle Unicode characters
        devnull = open(os.devnull, 'w', encoding='utf-8', errors='replace')
        sys.stdout = devnull
        sys.stderr = devnull
        return False  # No console available
    return True  # Console available

# Global flag for whether we have console output
HAS_CONSOLE = setup_output()

def log(message):
    """Print a message only if console is available."""
    if HAS_CONSOLE:
        print(message)

# When running as a PyInstaller bundle, we need to handle paths differently
def get_base_path():
    """Get the base path for resources, works both in dev and when frozen."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def setup_environment():
    """Set up the environment for the server."""
    base_path = get_base_path()
    
    # Change to the base directory so relative paths work
    os.chdir(base_path)
    
    # Ensure the generated directory exists
    generated_dir = os.path.join(base_path, "generated")
    os.makedirs(generated_dir, exist_ok=True)
    
    # Add base path to Python path for imports
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    return base_path

def open_browser(url):
    """Open the browser to the given URL."""
    log(f">>> Opening browser to {url}")
    webbrowser.open(url)

def open_browser_delayed(url, delay=1.5):
    """Open the browser after a delay to let the server start."""
    def _open():
        time.sleep(delay)
        open_browser(url)
    
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()

def create_icon_image():
    """Load or create the system tray icon image."""
    try:
        from PIL import Image
        log("PIL imported successfully")
    except ImportError as e:
        log(f"Failed to import PIL: {e}")
        return None
    
    try:
        base_path = get_base_path()
        
        # Try to load the dedicated tray icon PNG first (best quality)
        tray_icon_path = os.path.join(base_path, 'tray_icon.png')
        log(f"Looking for tray icon at: {tray_icon_path}")
        
        if os.path.exists(tray_icon_path):
            log("Tray icon PNG found, loading...")
            img = Image.open(tray_icon_path)
            log("Tray icon loaded successfully")
            return img
        
        # Fallback to ico file
        icon_path = os.path.join(base_path, 'icon.ico')
        log(f"Looking for icon.ico at: {icon_path}")
        
        if os.path.exists(icon_path):
            log("Icon file found, loading...")
            img = Image.open(icon_path)
            # Resize to 64x64 for tray
            img = img.resize((64, 64), Image.LANCZOS)
            log("Icon loaded and resized")
            return img
        
        log("No icon files found, creating fallback...")
        
        # Fallback: create a simple icon if no file found
        from PIL import ImageDraw
        size = 64
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Simple gear-like shape with FFXI colors
        gold = (201, 162, 39, 255)
        dark = (10, 14, 20, 255)
        
        # Outer circle
        draw.ellipse([4, 4, size-4, size-4], fill=dark, outline=gold, width=2)
        # Inner gold ring
        draw.ellipse([12, 12, size-12, size-12], fill=gold)
        # Center dark circle
        draw.ellipse([20, 20, size-20, size-20], fill=dark)
        # Center gold dot
        draw.ellipse([26, 26, size-26, size-26], fill=gold)
        
        log("Fallback icon created successfully")
        return img
    except Exception as e:
        log(f"Error creating icon: {e}")
        return None

def request_shutdown():
    """Request the server to shut down."""
    global server_instance
    log("\n>>> Shutdown requested...")
    shutdown_event.set()
    if server_instance:
        server_instance.should_exit = True

def setup_tray_icon(url):
    """Set up the system tray icon with menu."""
    try:
        import pystray
        from pystray import MenuItem as item
        log("pystray imported successfully")
    except ImportError as e:
        log(f"Note: pystray not available ({e}), running without system tray icon")
        return None
    
    icon_image = create_icon_image()
    if icon_image is None:
        log("Note: Could not create icon image, running without system tray icon")
        return None
    
    def on_open_browser(icon, item):
        open_browser(url)
    
    def on_stop_server(icon, item):
        request_shutdown()
        icon.stop()
    
    # Create menu
    menu = pystray.Menu(
        item('Open in Browser', on_open_browser, default=True),
        item('Stop Server', on_stop_server)
    )
    
    # Create icon
    icon = pystray.Icon(
        "FFXIGearOptimizer",
        icon_image,
        "FFXI Gear Optimizer",
        menu
    )
    
    return icon

def run_tray_icon(icon):
    """Run the tray icon in a separate thread."""
    if icon:
        def run():
            icon.run()
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread
    return None

def main():
    """Main entry point."""
    global server_instance
    
    log("=" * 60)
    log("  FFXI Gear Set Optimizer")
    log("=" * 60)
    log("")
    
    # Set up environment
    base_path = setup_environment()
    log(f"Working directory: {base_path}")
    log("")
    
    # Server configuration
    host = "127.0.0.1"
    port = 8080
    url = f"http://{host}:{port}"
    
    log(f"Starting server at {url}")
    log("Use the system tray icon or web UI to stop the server.")
    log("-" * 60)
    
    # Set up system tray icon
    tray_icon = setup_tray_icon(url)
    run_tray_icon(tray_icon)
    
    # Schedule browser open
    open_browser_delayed(url)
    
    # Import and run uvicorn
    try:
        import uvicorn
        from api import app
        
        # Create server config - disable logging entirely in windowed mode
        # log_config=None prevents uvicorn from configuring logging (avoids closed file errors)
        config_kwargs = dict(
            app=app,
            host=host,
            port=port,
            log_level="warning" if not HAS_CONSOLE else "info",
            access_log=HAS_CONSOLE,
        )
        if not HAS_CONSOLE:
            config_kwargs['log_config'] = None
        
        config = uvicorn.Config(**config_kwargs)
        server_instance = uvicorn.Server(config)
        
        # Run the server (this blocks until stopped)
        server_instance.run()
        
    except KeyboardInterrupt:
        log("\n\nServer stopped by user.")
    except Exception as e:
        log(f"\nError starting server: {e}")
        if HAS_CONSOLE:
            import traceback
            traceback.print_exc()
            print("\nPress Enter to exit...")
            input()
        sys.exit(1)
    finally:
        # Clean up tray icon
        if tray_icon:
            try:
                tray_icon.stop()
            except:
                pass
    
    log("\nServer stopped. Goodbye!")

if __name__ == "__main__":
    # CRITICAL: This MUST be the first thing called for multiprocessing to work
    # in frozen executables on Windows. Without this, child processes fail to
    # spawn correctly and Python falls back to single-process execution.
    import multiprocessing
    multiprocessing.freeze_support()
    
    main()