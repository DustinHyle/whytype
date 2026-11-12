# Updating Why Type

Already have Why Type installed? Here's how to move to the newest version.
**Your settings and downloaded speech models are kept** — you won't need to set
up your shortcut, microphone or model again.

**Download the latest version from the
[Releases page](https://github.com/DustinHyle/whytype/releases/latest).**
What changed in each version is listed in the [Changelog](CHANGELOG.md).

> **Which version do I have?** Open Why Type's **Settings** — the version is
> shown there. (Versions before 1.2.1 don't show it; if you don't see one,
> you're on an old version and should update.)

---

## 🪟 Windows

1. **Quit Why Type:** right-click the microphone icon in the system tray
   (bottom-right, near the clock — you may need to click the **^** arrow) and
   choose **Quit**.
2. On the [Releases page](https://github.com/DustinHyle/whytype/releases/latest),
   download the file ending in **`-windows.zip`**.
3. Right-click the downloaded file → **Extract All… → Extract**.
4. Open the extracted folder and **double-click `install.bat`**.
   - If a blue "Windows protected your PC" box appears, click
     **More info → Run anyway**.
   - ⚠️ The installer closes any running Python programs. If you use other
     Python apps, save your work in them first.
5. The installer says **"Why Type is already installed… Overwrite?"** — type
   **`Y`** and press **Enter**. This replaces the app only; your settings and
   models are not touched.
6. At **"Choose a model to download"**, type **`6`** (Skip) and press
   **Enter** to keep the model you already use. (Picking a model you already
   have is also fine — it won't download it again.)
7. When it finishes, open **Why Type** from the Start Menu.

---

## 🍎 Mac

1. **Quit Why Type:** click the Why Type icon in the menu bar (top-right of the
   screen) and choose **Quit**.
2. On the [Releases page](https://github.com/DustinHyle/whytype/releases/latest),
   download the file ending in **`-macos.zip`** and double-click it to unzip.
3. Drag the new **Why Type** into your **Applications** folder. When macOS asks,
   click **Replace**.
4. Open Why Type. Because it's a new download, macOS may block it once again,
   the same as the first time you installed it: click **Done** (⚠️ **not**
   "Move to Trash"), then go to **System Settings → Privacy & Security** and
   click **Open Anyway**.
5. **Turn Accessibility back on.** macOS treats each new version as a new app,
   so the old permission usually stops working even though its switch still
   looks on. If Why Type doesn't type after updating (or doesn't react to the
   shortcut):
   - Open **System Settings → Privacy & Security → Accessibility**.
   - Select **Why Type** and click the **−** button to remove it. (Do the same
     under **Input Monitoring** if Why Type is listed there.)
   - Quit and reopen Why Type, then allow it when macOS asks — or add it back
     with the **+** button and turn it on.
   - Quit and reopen Why Type once more.

**Installed it with Terminal (`install.sh`) in the past?** Older versions were
installed into the **Applications** folder inside your *home* folder
(`~/Applications/Why Type.app`). After installing the new version, delete that
old copy (drag it to the Trash) so you don't accidentally start it — then use
the one in the main **Applications** folder.

---

## 🐧 Linux

1. **Quit Why Type** from its tray icon menu.
2. On the [Releases page](https://github.com/DustinHyle/whytype/releases/latest),
   download the file ending in **`-linux.zip`** and extract it.
3. In a terminal in the extracted folder, run:
   ```bash
   ./install.sh
   ```
4. At **"Why Type is already installed. Overwrite?"** type **`y`**.
5. At **"Choose a model to download"**, type **`6`** (Skip) to keep the model
   you already use.
6. Launch **Why Type** from your applications menu.

---

## Where your settings and models live

Updating only replaces the app. These folders are left alone, which is why your
settings and models carry over:

| | Settings | Downloaded models |
|---|---|---|
| Windows | `%LOCALAPPDATA%\WhyType\WhyType\settings.json` | `%LOCALAPPDATA%\WhyType\WhyType\Cache\models` |
| Mac | `~/Library/Application Support/WhyType/settings.json` | `~/Library/Caches/WhyType/models` |
| Linux | `~/.config/WhyType/settings.json` | `~/.cache/WhyType/models` |

> **Windows:** the installers in versions up to 1.2.3 reset Why Type's
> settings (shortcut, microphone, and so on) to their defaults whenever you
> updated. That's fixed from 1.2.4 on. If an earlier update changed your
> shortcut or microphone, set them again in **Settings** once; future updates
> will keep them.

---

## Something not working after the update?

- **Mac — nothing gets typed, or the shortcut does nothing:** redo step 5 of
  the Mac section (remove and re-add Why Type under Accessibility).
- **Windows — "Why Type is still running" during install:** open Task Manager,
  end any **WhyType** or **pythonw** processes, then press a key in the
  installer window to continue.
- Still stuck? Open an issue on the
  [GitHub Issues page](https://github.com/DustinHyle/whytype/issues) with your
  log file attached. On Windows it's
  `%LOCALAPPDATA%\WhyType\WhyType\Logs\whytype.log`; on Mac it's
  `~/Library/Logs/WhyType/whytype.log`.
