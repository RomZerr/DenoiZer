import sys
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": ["os", "sys", "json", "subprocess", "OpenImageIO", "OpenEXR", "Imath", "time", "PySide2"],
    "excludes": [],
    "include_files": ["user_config.json", "DenoiZer_icon.png", "ExrMerge.py", "Integrator_Denoizer.py"],
}

# Base for Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Use this to hide the console window

setup(
    name="DenoiZer",
    version="1.0",
    description="RenderMan Denoiser and EXR processing application",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "DenoiZer.py",
            base=base,
            icon="DenoiZer_icon.png",
            target_name="DenoiZer.exe"
        )
    ],
) 