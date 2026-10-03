cmake_minimum_required(VERSION 3.20)
project(ivcore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Unreal builds with exceptions and RTTI disabled; the core must too (CLAUDE.md).
set(IV_FLAGS -Wall -Wextra -Werror -fno-exceptions -fno-rtti)

file(GLOB IV_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp)
add_library(ivcore STATIC ${IV_SOURCES})
target_include_directories(ivcore PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(ivcore PRIVATE ${IV_FLAGS})

# Headless duel simulator: AI vs AI, CSV events + summary (docs/BALANCE_REPORT.md).
add_executable(ivsim tools/ivsim.cpp)
target_link_libraries(ivsim PRIVATE ivcore)
target_compile_options(ivsim PRIVATE ${IV_FLAGS})

enable_testing()
file(GLOB IV_TEST_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tests/*.cpp)
add_executable(iv_tests ${IV_TEST_SOURCES})
target_link_libraries(iv_tests PRIVATE ivcore)
target_compile_options(iv_tests PRIVATE ${IV_FLAGS})

# One ctest entry per module so a failure points at the module (filter = "Module.").
foreach(module IN ITEMS Body Resources Strike Defense Ai Determinism Sim)
  add_test(NAME ${module} COMMAND iv_tests "${module}.")
endforeach()
