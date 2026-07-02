[app]
title = Referee Tracker
package.name = referee_tracker
package.domain = org.referee.tracker

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,pdf
source.include_patterns = data/*.json,app/*,*.pdf

# Exclude desktop-only code and build artifacts
source.exclude_dirs = bin,.buildozer,__pycache__,app/ui,assets
source.exclude_patterns = main_mobile.py,run_app.py,app/data_manager.py,app/handball_content.py

version = 1.0.0

requirements = python3,kivy==2.3.1,pillow,pymysql,android,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 31
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
# FileProvider: androidx core + the provider_paths.xml resource. The <provider>
# element itself is injected into <application> via a patched manifest template
# (extra_manifest_xml injects at <manifest> level which AAPT rejects).
android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.6.0
android.res_xml = provider_paths.xml

[buildozer]
log_level = 2
warn_on_root = 0
