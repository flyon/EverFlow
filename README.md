# EverFlow

EverFlow is a small macOS session flow helper for keeping a local desktop session awake during long-running work.

It runs quietly from a terminal, waits for a period of inactivity, then keeps the session from settling into idle. When you return and use the machine again, it pauses automatically and waits for the next idle window.

## Run

```bash
python3 everflow_headless.py
```

## Stop

Press `Ctrl+C` in the terminal, close the terminal, or terminate the process.

## Permission

macOS requires Accessibility permission for the terminal app that runs the script:

System Settings -> Privacy & Security -> Accessibility

Enable Terminal, iTerm, or whichever terminal you use.

## Notes

- macOS only.
- No Python packages are required.
- Defaults to the centered third of the main display.
- Auto-starts after 3 minutes of inactivity.
