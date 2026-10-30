# 构建宿主解释器；CTest 使用同一编译器重新构建测试用 VM 和嵌入包装程序。

cmake_minimum_required(VERSION 3.16)
project(c4vm LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
add_executable(c4vm c4vm.c)
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(c4vm PRIVATE -Wall -Wextra -Wpedantic)
endif()

include(CTest)
if(BUILD_TESTING)
    find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
    add_test(NAME regression COMMAND ${Python3_EXECUTABLE} -m unittest discover -v)
    set_tests_properties(regression PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        ENVIRONMENT "CC=${CMAKE_C_COMPILER}" TIMEOUT 120)
endif()
