set(CMAKE_INSTALL_PREFIX /usr)
cmake_minimum_required(VERSION 3.13)
project(ttymidi-rpi)

# Sources
file(GLOB sources *.c)

# Checks
find_library(ASOUND_LIB NAMES asound REQUIRED)

# Build
add_executable(ttymidi ${sources})
target_link_libraries(ttymidi PRIVATE asound pthread)

# Install
install(TARGETS ttymidi DESTINATION bin)
