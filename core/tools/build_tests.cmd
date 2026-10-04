@echo off
rem Builds and runs the core tests on Windows (MSVC + Ninja from Visual Studio). Run through the F:\IVRepo junction (the repo path has Cyrillic letters).
set VS=C:\Program Files\Microsoft Visual Studio\18\Insiders
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul
set CM=%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe
set NINJA=%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe
"%CM%" -S F:\IVRepo\core -B F:\IVBuild\core -G Ninja -DCMAKE_MAKE_PROGRAM="%NINJA%" -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1
"%CM%" --build F:\IVBuild\core
if errorlevel 1 exit /b 1
"%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\ctest.exe" --test-dir F:\IVBuild\core --output-on-failure
