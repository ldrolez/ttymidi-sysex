cmake_minimum_required(VERSION 3.18)
project(ttymidi-rpi)

# Sources
file(GLOB sources *.c)

# Checks
find_library(ASOUND_LIB NAMES asound REQUIRED)

# Build
add_executable(ttymidi ${sources})
target_link_libraries(ttymidi PRIVATE asound pthread)
