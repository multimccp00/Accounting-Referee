# Mobile and Desktop Setup Guide

This app is available in two versions:

1. **Tkinter Desktop Version** - Traditional desktop app (improved modern UI coming)
2. **Kivy Mobile Version** - Material Design app for desktop and Android phones

## Running the Tkinter Desktop Version

```bash
python -m app.ui.app
```

## Running the Kivy Mobile Version (Desktop Testing)

The Kivy version uses Material Design and is optimized for mobile but also works on desktop.

```bash
python app/mobile/main.py
```

This will open a mobile-sized window (540x960) that you can test on your desktop.

## Building Android APK

### Prerequisites

You'll need:
- Java Development Kit (JDK) 11+
- Android SDK
- Android NDK
- Python 3.10+

On Windows, the easiest way is to use Buildozer with Cygwin:

1. **Install Buildozer:**
   ```bash
   pip install buildozer cython
   ```

2. **Build the APK:**
   ```bash
   buildozer android debug
   ```

   Or for release:
   ```bash
   buildozer android release
   ```

3. **The APK will be in:** `bin/referee_tracker-1.0.0-debug.apk`

### Using Linux/WSL for Building (Recommended)

Building Android APKs is much easier on Linux. If you're on Windows, use WSL2:

```bash
# In WSL2
wsl --install

# Then in WSL:
sudo apt-get update
sudo apt-get install python3-pip openjdk-11-jdk-headless android-sdk

pip install buildozer cython

buildozer android debug
```

### Installing on Android Device

#### Via USB (Connected to PC):
```bash
adb install -r bin/referee_tracker-1.0.0-debug.apk
```

#### Via File Transfer:
Copy the `.apk` file to your Android phone and open it with a file manager to install.

## Features in Each Version

### Tkinter Version
- Game tracking and earnings management
- Rulebook PDF viewer with search
- Quiz/testing system with progress tracking
- Statistics and analytics
- Import games from Excel
- Traditional desktop interface

### Kivy/Mobile Version
- **All Tkinter features** (being migrated)
- Material Design UI
- Touch-optimized interface
- Responsive design (works on any screen size)
- Offline-first (data stored locally)
- Works on Android phones and tablets
- Desktop testing support

## Data Sync

Both versions share the same data:
- Games stored in `data/all_games.json` or database
- Test progress in `data/test_progress.json`
- Rulebook content in `data/handball_content.json`

You can switch between versions and your data will be preserved.

## Development

### Adding a New Feature

1. Implement in **both** versions:
   - Tkinter: `app/ui/app.py`
   - Kivy: `app/mobile/main.py`

2. Or implement in Tkinter first, then port to Kivy later

### Kivy App Structure

- `app/mobile/main.py` - Main Kivy app with Material Design screens
- `buildozer.spec` - Android build configuration
- Shared data models from `app/game_tracking/` and `app/rulebook/`

## Troubleshooting

### Kivy Window Won't Open
```bash
# Check if SDL2 drivers are installed
python -m pip install --upgrade kivy kivy_deps.sdl2
```

### APK Build Fails
```bash
# Clean previous builds
buildozer android clean

# Rebuild
buildozer android debug
```

### Data Not Syncing Between Versions
- Ensure both versions use the same data directory (`data/`)
- Check file permissions
- Verify JSON files are valid

## Next Steps

1. Test the Kivy version on desktop
2. Refine Material Design UI based on feedback
3. Build and test APK on Android device
4. Migrate remaining features from Tkinter to Kivy
5. Deprecated Tkinter version once Kivy is complete
