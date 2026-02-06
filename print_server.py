import os
import sys
import json
import time
import threading
import platform
import subprocess
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pystray
from PIL import Image, ImageDraw

# Try importing tkinter, handle failure
TK_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    print("Tkinter not found. Will use fallbacks where available.")

# Configuration file path
# Store config in the same directory as the script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.json')

# Global state
config = {
    "monitor_folder": "",
    "selected_printer": ""
}
observer = None
icon = None

def load_config():
    global config
    print(f"Loading config from: {CONFIG_FILE}")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_printers():
    system_platform = platform.system()
    printers = []
    
    if system_platform == "Darwin":  # macOS
        try:
            result = subprocess.run(['lpstat', '-a'], capture_output=True, text=True)
            output = result.stdout
            for line in output.splitlines():
                if line.strip():
                    parts = line.split()
                    if parts:
                        printers.append(parts[0])
        except Exception as e:
            print(f"Error listing printers on Mac: {e}")
            
    elif system_platform == "Windows":
        try:
            import win32print
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printer_configs = win32print.EnumPrinters(flags, None, 1)
            for printer_info in printer_configs:
                printers.append(printer_info[2])
        except ImportError:
            return ["Error: win32print missing"]
        except Exception as e:
            print(f"Error listing printers on Windows: {e}")
            
    return printers

def send_file_to_printer(file_path, printer_name):
    system_platform = platform.system()
    print(f"Printing {file_path} to {printer_name}...")
    
    if system_platform == "Darwin":
        try:
            cmd = ['lp', '-d', printer_name, '-o', 'raw', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("Print command sent successfully.")
                return True
            else:
                print(f"Print error: {result.stderr}")
                return False
        except Exception as e:
            print(f"Exception printing on Mac: {e}")
            return False

    elif system_platform == "Windows":
        try:
            import win32print
            hPrinter = win32print.OpenPrinter(printer_name)
            try:
                hJob = win32print.StartDocPrinter(hPrinter, 1, ("ZPL Print Job", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    win32print.WritePrinter(hPrinter, data)
                    win32print.EndPagePrinter(hPrinter)
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
                
            print("Print job sent successfully.")
            return True
        except Exception as e:
            print(f"Exception printing on Windows: {e}")
            return False

    return False

class ZPLHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.zpl'):
            self.process_file(event.src_path)

    def process_file(self, file_path):
        time.sleep(0.5) 
        printer_name = config.get("selected_printer")
        if not printer_name:
            print("No printer selected. Skipping print.")
            return

        if send_file_to_printer(file_path, printer_name):
            try:
                base, ext = os.path.splitext(file_path)
                new_path = base + ".dat"
                if os.path.exists(new_path):
                    os.replace(file_path, new_path)
                else:
                    os.rename(file_path, new_path)
                print(f"Renamed {file_path} to {new_path}")
            except Exception as e:
                print(f"Error renaming file: {e}")

def start_monitoring():
    global observer
    folder = config.get("monitor_folder")
    
    if observer:
        observer.stop()
        observer.join()
        observer = None

    if folder and os.path.isdir(folder):
        print(f"Starting monitor on {folder}")
        event_handler = ZPLHandler()
        observer = Observer()
        observer.schedule(event_handler, folder, recursive=False)
        observer.start()
    else:
        print("Monitor folder not configured or invalid.")

def stop_monitoring():
    global observer
    if observer:
        observer.stop()
        observer.join()
        observer = None

def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (255, 255, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill="black")
    dc.rectangle((20, 10, 44, 16), fill="gray")
    return image

# --- Helper functions for macOS dialogs via AppleScript ---
def mac_choose_folder():
    try:
        script = 'choose folder with prompt "Select Folder to Monitor"'
        cmd = ['osascript', '-e', script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # Output format: alias Macintosh HD:Users:...
            path_str = result.stdout.strip()
            # Convert alias to POSIX path
            if "alias " in path_str:
                path_str = path_str.replace("alias ", "")
            # We need to convert HFS path to POSIX if needed, but 'choose folder' returns alias. 
            # Actually easier: 'POSIX path of (choose folder)'
            script = 'POSIX path of (choose folder with prompt "Select Folder to Monitor")'
            cmd = ['osascript', '-e', script]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout.strip()
    except Exception as e:
        print(f"Error in mac_choose_folder: {e}")
    return None

def mac_choose_from_list(items, prompt):
    try:
        # items need to be a string check "item 1", "item 2"
        # AppleScript list format: {"a", "b", "c"}
        quoted_items = [f'"{i}"' for i in items]
        list_str = "{" + ",".join(quoted_items) + "}"
        script = f'choose from list {list_str} with prompt "{prompt}"'
        cmd = ['osascript', '-e', script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            val = result.stdout.strip()
            if val == "false": # User cancelled
                return None
            return val
    except Exception as e:
        print(f"Error in mac_choose_from_list: {e}")
    return None

def select_folder():
    folder_selected = None
    if TK_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes('-topmost', True)
        current = config.get("monitor_folder", "")
        folder_selected = filedialog.askdirectory(initialdir=current if current else None, title="Select Folder to Monitor")
        root.destroy()
    elif platform.system() == "Darwin":
        folder_selected = mac_choose_folder()
    else:
        print("GUI libraries not found. Configure manually in config.json")
    
    if folder_selected:
        config["monitor_folder"] = folder_selected
        save_config()
        start_monitoring()
        show_status()

def select_printer():
    printers = get_printers()
    if not printers:
        show_notification("No printers found.")
        return

    selected_value = None
    
    if TK_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        dialog = tk.Toplevel(root)
        dialog.title("Select Printer")
        dialog.geometry("300x250")
        dialog.attributes('-topmost', True)
        tk.Label(dialog, text="Available Printers:").pack(pady=5)
        listbox = tk.Listbox(dialog)
        listbox.pack(expand=True, fill="both", padx=10, pady=5)
        for p in printers:
            listbox.insert("end", p)
        current_printer = config.get("selected_printer")
        if current_printer in printers:
            idx = printers.index(current_printer)
            listbox.selection_set(idx)
            listbox.activate(idx)
        
        container = [None]
        def on_ok():
            sel = listbox.curselection()
            if sel:
                container[0] = listbox.get(sel[0])
            dialog.destroy()
        tk.Button(dialog, text="OK", command=on_ok).pack(pady=5)
        dialog.wait_window()
        root.destroy()
        selected_value = container[0]
        
    elif platform.system() == "Darwin":
        selected_value = mac_choose_from_list(printers, "Select Printer")
    else:
         print("GUI libraries not found. Configure manually in config.json")

    if selected_value:
        config["selected_printer"] = selected_value
        save_config()
        show_status()

def show_status():
    folder = config.get("monitor_folder", "Not set")
    printer = config.get("selected_printer", "Not set")
    msg = f"Monitoring: {folder}\nPrinter: {printer}"
    show_notification(msg)

def show_notification(msg):
    if icon:
        icon.notify(msg, title="ZPL Print Server")
    else:
        print(f"Notification: {msg}")

def exit_action(icon_item):
    stop_monitoring()
    icon.stop()

def get_folder_label(item):
    folder = config.get("monitor_folder")
    if folder:
        # Shorten if too long
        if len(folder) > 30:
            folder = "..." + folder[-27:]
        return f"Folder: {folder}"
    return "Select Folder..."

def get_printer_label(item):
    printer = config.get("selected_printer")
    return f"Printer: {printer}" if printer else "Select Printer..."

def setup_menu():
    return pystray.Menu(
        pystray.MenuItem("Status", lambda icon, item: show_status()),
        pystray.MenuItem(get_folder_label, lambda icon, item: select_folder()),
        pystray.MenuItem(get_printer_label, lambda icon, item: select_printer()),
        pystray.MenuItem("Exit", lambda icon, item: exit_action(icon))
    )

def main():
    global icon
    load_config()
    start_monitoring()
    
    icon_image = create_image()
    menu = setup_menu()
    
    icon = pystray.Icon("ZPLPrintServer", icon_image, "ZPL Print Server", menu)
    
    try:
        icon.run()
    except KeyboardInterrupt:
        stop_monitoring()

# --- Flask Server for Remote Printing ---
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask not found. HTTP printing disabled.")

def run_flask_app():
    if not FLASK_AVAILABLE:
        return

    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    @app.route('/print', methods=['POST'])
    def print_zpl():
        try:
            data = request.json
            zpl_content = data.get('zpl')
            
            if not zpl_content:
                return jsonify({"error": "No ZPL content provided"}), 400
            
            # Save to monitor folder
            folder = config.get("monitor_folder")
            if not folder or not os.path.isdir(folder):
                return jsonify({"error": "Monitor folder not configured"}), 500
            
            # Create a unique filename
            timestamp = int(time.time() * 1000)
            filename = f"print_job_{timestamp}.zpl"
            file_path = os.path.join(folder, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(zpl_content)
                
            return jsonify({"message": "Print job queued", "file": filename}), 200
            
        except Exception as e:
            print(f"Error in /print endpoint: {e}")
            return jsonify({"error": str(e)}), 500

    print("Starting Flask server on port 9999 (Available on Network)...")
    # Run without debug to avoid main thread issues, and use different port if needed
    app.run(host='0.0.0.0', port=9999)

def start_flask_thread():
    if FLASK_AVAILABLE:
        flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        flask_thread.start()

if __name__ == "__main__":
    start_flask_thread()
    main()
