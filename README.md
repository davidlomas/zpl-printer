# ZPL Print Server

A cross-platform system tray application (Windows & macOS) that monitors a folder for ZPL files and automatically sends them to a configured printer. It also includes a Flask-based API for remote printing.

## Features

- **Folder Monitoring**: Automatically detects `.zpl` files in a selected directory.
- **Auto-Printing**: Sends ZPL content directly to the selected printer (RAW mode).
- **System Tray Integration**: Application runs in the background with a system tray icon for easy configuration.
- **Cross-Platform**: Works on MacOS (using `lp` command) and Windows (using `win32print`).
- **HTTP API**: Built-in Flask server to accept ZPL jobs via HTTP POST requests (Port 9999).
- **File Management**: Automatically renames printed files from `.zpl` to `.dat` to indicate completion.

## Requirements

- Python 3.x
- Dependencies listed in `requirements.txt`

## Installation

1.  Clone the repository or download the source code.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

    > **Note for Windows Users**: The `pywin32` library is required and should be installed automatically via `requirements.txt`.

## Usage

1.  Run the application:

    ```bash
    python print_server.py
    ```

2.  A system tray icon (white square with a smaller inner square) will appear.
3.  **Right-click** (or click) the tray icon to open the menu.
4.  **Select Printer**: Choose the printer you want to use from the list.
5.  **Select Folder**: Choose the local folder you want to monitor.
6.  The application is now active. Any `.zpl` file dropped into the monitored folder will be printed and renamed.

## API Usage

The application starts a local HTTP server on port **9999**. You can send print jobs programmatically.

### Endpoint: `POST /print`

**URL**: `http://localhost:9999/print`

**Payload (JSON)**:
```json
{
  "zpl": "^XA^FO50,50^ADN,36,20^FDHello World^FS^XZ"
}
```

**Response**:
- `200 OK`: Job queued successfully.
- `400 Bad Request`: Missing ZPL content.
- `500 Internal Server Error`: Configuration or system error.

## Configuration

Settings are saved automatically to `config.json` in the application directory.

```json
{
    "monitor_folder": "/path/to/monitor",
    "selected_printer": "Printer_Name"
}
```

## Notes

- **MacOS**: Uses the system `lp` command. Ensure your printer is correctly installed in system settings.
- **Windows**: Uses Windows Print Spooler API.
- **GUI**: If `tkinter` is available, standard dialogs are used. On MacOS, it falls back to AppleScript dialogs if `tkinter` is not present, though `tkinter` is recommended.
