# EverFlow

EverFlow is a small session flow helper for keeping a local desktop session awake during long-running work.

It runs quietly from a terminal, waits for a period of inactivity, then keeps the session from settling into idle. When you return and use the machine again, it pauses automatically and waits for the next idle window.

## Run

```bash
python3 everflow_headless.py
```

## Stop

Press `Ctrl+C` in the terminal, close the terminal, or terminate the process.

## Platform Notes

### macOS

macOS requires Accessibility permission for the terminal app that runs the script:

System Settings -> Privacy & Security -> Accessibility

Enable Terminal, iTerm, or whichever terminal you use.

### Windows

Run from Command Prompt, PowerShell, or Windows Terminal:

```powershell
python everflow_headless.py
```

No Python packages are required. If the script is not able to affect the current desktop session, run the terminal normally in the same user session as the display you want to keep active.

## Notes

- Supports macOS and Windows.
- No Python packages are required.
- Defaults to the centered third of the main display.
- Auto-starts after 3 minutes of inactivity.
