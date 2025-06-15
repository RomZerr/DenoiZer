@echo off
echo Activation de l'environnement virtuel...
call .venv\Scripts\activate.bat

echo Installation des dépendances requises...
pip install --upgrade pip
pip install pyinstaller
pip install PySide6
pip install numpy
pip install OpenEXR
pip install OpenImageIO
pip install psutil
pip uninstall -y PySide2

echo Vérification de l'installation de OpenImageIO...
python -c "import OpenImageIO; print('OpenImageIO installé')" || (
    echo ERREUR: OpenImageIO n'est pas installé correctement.
    pause
    exit /b 1
)

echo Compilation de DenoiZer...
pyinstaller --clean --noconfirm ^
  --name DenoiZer ^
  --icon=DenoiZer_icon.ico ^
  --add-data "DenoiZer_icon.png;." ^
  --add-data "DenoiZer_icon.ico;." ^
  --add-data "ExrMerge.py;." ^
  --add-data "Integrator_Denoizer.py;." ^
  --add-data "fonts\\CutePixel.ttf;fonts" ^
  --add-data "fonts\\Minecrafter.Alt.ttf;fonts" ^
  --hidden-import numpy ^
  --hidden-import numpy.core ^
  --hidden-import numpy.core._methods ^
  --hidden-import numpy.lib.format ^
  --noconsole ^
  --onedir ^
  DenoiZer.py

echo Compilation terminée!

echo IMPORTANT: Avant de distribuer cette application, assurez-vous que Visual C++ Redistributable 2019 est installé.
echo Téléchargez-le depuis: https://aka.ms/vs/16/release/vc_redist.x64.exe

powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('DenoiZer.lnk'); $s.TargetPath='%~dp0dist\DenoiZer\DenoiZer.exe'; $s.IconLocation='%~dp0DenoiZer_icon.ico'; $s.Save()"

echo Création du raccourci terminée!
pause 