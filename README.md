# EverFlow

EverFlow is a small session flow helper for keeping a local desktop session awake during long-running work.

It runs quietly from a terminal, waits for a period of inactivity, then keeps the session from settling into idle. When you return and use the machine again, it pauses automatically and waits for the next idle window.

## Run

With Node/npm installed:

```bash
npx github:flyon/EverFlow
```

With an automatic evening pause and user-activity resume:

```bash
npx github:flyon/EverFlow --autoPause=6pm --autoResume
```

Minimal terminal output:

```bash
npx github:flyon/EverFlow --autoPause=18:00 --autoResume --silent
```

Keep activity scoped to VS Code:

```bash
npx github:flyon/EverFlow --autoPause=18:00 --autoResume --targetApp=vscode
```

With VS Code targeting, lunch pause, and evening pause:

```bash
npx github:flyon/EverFlow --targetApp=vscode --lunchPause=13:00-14:00 --autoPause=18:00 --autoResume
```

Or run the Python file directly:

```bash
python3 everflow_headless.py
```

```bash
python3 everflow_headless.py --autoPause=18:00 --autoResume
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
- Optional `--autoPause` accepts local times like `6pm`, `6:30pm`, `18:00`, or `1830`.
- The auto-pause time is randomized by +/-10 minutes by default; adjust with `--pauseJitterMinutes=0`.
- With `--autoResume`, a scheduled pause stays active overnight and resumes only after user input before the next pause time.
- Optional `--lunchPause=13:00-14:00` pauses for that exact bounded window and resumes automatically afterward.
- Optional `--targetApp=vscode` checks/focuses VS Code at startup, returns to the terminal, maximizes VS Code on Windows before activity, and pauses later if VS Code cannot be focused.
- Optional `--silent` hides operational logs after a short startup animation.
