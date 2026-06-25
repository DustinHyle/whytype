# Installing Why Type

Why Type is a voice dictation app: hold a keyboard shortcut, speak, and your
words are typed into whatever app you're using. It runs entirely on your
computer — nothing is sent to the cloud.

**Download the latest version from the
[Releases page](https://github.com/DustinHyle/whytype/releases/latest).**
Pick the file for your computer below.

---

## 🪟 Windows

1. On the [Releases page](https://github.com/DustinHyle/whytype/releases/latest),
   download **`whytype-windows.zip`**.
2. Find the downloaded file (usually in your **Downloads** folder),
   **right-click it → "Extract All…" → Extract**.
3. Open the extracted folder and **double-click `install.bat`**.
   - If Windows shows a blue "Windows protected your PC" box, click
     **More info → Run anyway** (this happens because the app isn't from the
     Microsoft Store).
   - The installer sets everything up for you. If it asks about a model, just
     press **Enter** to use the recommended one.
4. When it finishes, open **Why Type** from the Start Menu.

**Using it:** hold **Ctrl + Win**, speak, then let go — your words get typed.
Look for the small microphone icon in the system tray (bottom-right, near the
clock; you may need to click the **^** arrow to see it). Right-click it for
Settings.

---

## 🍎 Mac

1. On the [Releases page](https://github.com/DustinHyle/whytype/releases/latest),
   download **`whytype-macos-standalone.zip`**.
2. Double-click the downloaded file to unzip it. You'll get **Why Type**.
3. Drag **Why Type** into your **Applications** folder.
4. **The first time only:** right-click (or Control-click) **Why Type** in
   Applications and choose **Open**, then click **Open** in the dialog. (This
   one-time step is needed because the app isn't from the Mac App Store.)
5. When you first use it, macOS will ask for **Microphone** and
   **Accessibility** permission — click **Allow / Open System Settings** and
   turn **Why Type** on. Accessibility is required for the app to type for you.
   After enabling it, quit and reopen Why Type.

**Using it:** hold **Ctrl + Cmd**, speak, then let go — your words get typed.
Look for the microphone icon in the menu bar (top-right of the screen). Click
it for Settings.

---

## 🐧 Linux

1. On the [Releases page](https://github.com/DustinHyle/whytype/releases/latest),
   download **`whytype-linux.zip`**.
2. Extract it, then from a terminal in that folder run:
   ```bash
   ./install.sh
   ```
   The installer checks for what it needs and tells you if anything is missing.
   Press **Enter** at the model prompt to use the recommended one.
3. Launch **Why Type** from your applications menu.

**Notes:**
- For microphone capture, install PortAudio if prompted
  (`sudo apt install libportaudio2` on Debian/Ubuntu).
- For GPU acceleration, install the Vulkan loader + drivers
  (`sudo apt install libvulkan1 mesa-vulkan-drivers`). Without it the app still
  works on the CPU.
- Global hotkeys/typing are most reliable under **X11**; Wayland support is
  limited.

**Using it:** hold **Ctrl + Super (the Windows key)**, speak, then let go.

---

## Picking a model

Why Type transcribes with a downloadable speech model. The installer offers a
few, and **Small** (the recommended default) is a good balance of speed and
accuracy for most people. You can switch models anytime in **Settings**.

| Model | Size | Best for |
|-------|------|----------|
| Tiny | ~75 MB | Older computers, simple clear speech |
| Base | ~142 MB | Everyday use, fast |
| **Small** | ~466 MB | **Recommended — good accuracy for most users** |
| Medium / Turbo | ~1.5 GB | Higher accuracy |
| Large | ~3.1 GB | Maximum accuracy, slowest |

---

## Need help?

Open an issue on the
[GitHub Issues page](https://github.com/DustinHyle/whytype/issues) and include
what happened. On Windows the log is at
`%LOCALAPPDATA%\WhyType\WhyType\Logs\whytype.log`; on Mac it's at
`~/Library/Logs/WhyType/whytype.log`.
