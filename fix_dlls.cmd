@echo off
echo Correction des DLLs problématiques...

REM Vérifier si le dossier dist existe
if not exist dist (
    echo Erreur: Le dossier dist n'existe pas. Veuillez d'abord compiler l'application avec build.cmd.
    goto :end
)

REM Vérifier si le dossier shiboken2 existe
if not exist dist\DenoiZer\_internal\shiboken2 (
    echo Note: Le dossier shiboken2 n'existe pas ou n'est pas au chemin attendu.
    echo Recherche des DLLs problématiques dans tout le dossier _internal...
    
    REM Rechercher les DLLs problématiques dans tout le dossier _internal
    for /r dist\DenoiZer\_internal %%F in (MSVCP140.dll VCRUNTIME140.dll VCRUNTIME140_1.dll) do (
        echo Renommage de %%F
        ren "%%F" "%%~nF.dll.bak"
    )
) else (
    echo Renommage des DLLs dans le dossier shiboken2...
    cd dist\DenoiZer\_internal\shiboken2
    if exist MSVCP140.dll ren MSVCP140.dll MSVCP140.dll.bak
    if exist VCRUNTIME140.dll ren VCRUNTIME140.dll VCRUNTIME140.dll.bak
    if exist VCRUNTIME140_1.dll ren VCRUNTIME140_1.dll VCRUNTIME140_1.dll.bak
    cd ..\..\..
)

echo Correction terminée. Assurez-vous d'installer Visual C++ Redistributable 2019 avant d'exécuter l'application.
echo Téléchargez-le depuis: https://aka.ms/vs/16/release/vc_redist.x64.exe

:end
pause 