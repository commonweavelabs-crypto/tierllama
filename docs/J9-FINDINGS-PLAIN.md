# J9 in plain language: install it like an app

## The one-command install
```
git clone https://github.com/commonweavelabs-crypto/tierllama
cd tierllama
install.bat
```
Five steps, zero Python knowledge required: check Python, install the pieces,
detect Ollama (with a plain message if it's missing), set up auto-start, and
open the dashboard. Updating later is `update.bat` - pull and restart.

## The desktop-app trick (no Electron needed)

That thing Chrome does - the "install app" that gives Telegram its own icon and
taskbar entry? It's called a PWA, and it needs exactly two small files: a
manifest (the app's name, colors, icon) and a service worker (offline shell).
Tierllama ships both, plus a llama icon we drew in code.

Click Install in Chrome's address bar and Tierllama gets its own window, its
own icon on your desktop and taskbar - indistinguishable from a native app,
but still the same lightweight dashboard served by the router you already have.

## Why this matters
J1-J8 built the machine. J9 makes it installable. "Download this, run one file,
press Optimize" - that's the whole user story now.
