cmake_minimum_required(VERSION 3.20)
project(ivcore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Unreal builds with exceptions and RTTI disabled; the core must too (CLAUDE.md).
if(MSVC)
  # MSVC build (CI job 'msvc'): warnings as errors, no RTTI, exceptions disabled for our own code.
  set(IV_FLAGS /W4 /WX /GR- /EHs-c- /D_HAS_EXCEPTIONS=0 /permissive- /D_CRT_SECURE_NO_WARNINGS)   # the sim tool uses fopen
else()
  set(IV_FLAGS -Wall -Wextra -Werror -fno-exceptions -fno-rtti)
endif()

file(GLOB IV_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp)
add_library(ivcore STATIC ${IV_SOURCES})
target_include_directories(ivcore PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(ivcore PRIVATE ${IV_FLAGS})

# Headless duel simulator: AI vs AI, CSV events + summary (docs/BALANCE_REPORT.md).
add_executable(ivsim tools/ivsim.cpp)
target_link_libraries(ivsim PRIVATE ivcore)
target_compile_options(ivsim PRIVATE ${IV_FLAGS})

# The documented game loop (docs/CORE_API.md) as a runnable example, kept honest by CTest.
add_executable(iv_example examples/game_loop.cpp)
target_link_libraries(iv_example PRIVATE ivcore)
target_compile_options(iv_example PRIVATE ${IV_FLAGS})

enable_testing()
file(GLOB IV_TEST_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tests/*.cpp)
add_executable(iv_tests ${IV_TEST_SOURCES})
target_link_libraries(iv_tests PRIVATE ivcore)
target_compile_options(iv_tests PRIVATE ${IV_FLAGS})

# One ctest entry per module so a failure points at the module (filter = "Module.").
foreach(module IN ITEMS Body Resources Strike Defense Ai Determinism Sim Weapons Ultimate Presentation Anim Dummy Clash Dodge Stun Status External Boarding Special Lunge Jump Lock AirChop Berserk Breakdown)
  add_test(NAME ${module} COMMAND iv_tests "${module}.")
endforeach()
add_test(NAME Example COMMAND iv_example)
