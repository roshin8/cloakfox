# Portions Copyright (c) 2014 The Chromium Embedded Framework Authors.
# Helper bundle construction follows the CEF BSD-licensed sample.
# See THIRD_PARTY_LICENSES/CEF-LICENSE.txt.
cmake_minimum_required(VERSION 3.21)
project(CloakfoxChromium LANGUAGES C CXX OBJCXX)
if(NOT APPLE)
  message(FATAL_ERROR "This prototype currently supports macOS arm64 only")
endif()
set(CMAKE_CXX_STANDARD 20)
set(PROJECT_ARCH arm64 CACHE STRING "CEF distribution architecture")
if(NOT PROJECT_ARCH STREQUAL "arm64")
  message(FATAL_ERROR "Use the pinned macOS arm64 CEF distribution")
endif()
if(NOT CEF_ROOT)
  message(FATAL_ERROR "Set CEF_ROOT to the extracted pinned CEF distribution")
endif()
set(USE_SANDBOX ON CACHE BOOL "Sandbox is required" FORCE)
list(APPEND CMAKE_MODULE_PATH "${CEF_ROOT}/cmake")
find_package(CEF REQUIRED)
file(READ "${CEF_ROOT}/include/cef_version.h" _cef_version)
if(NOT _cef_version MATCHES "154\\.0\\.34\\+g14c5a08\\+chromium-154\\.0\\.8037\\.98")
  message(FATAL_ERROR "CEF version differs from cef-lock.json; review and update the pin before building")
endif()
add_subdirectory("${CEF_LIBCEF_DLL_WRAPPER_PATH}" libcef_dll_wrapper)
set(CEF_TARGET CloakfoxChromium)
SET_CEF_TARGET_OUT_DIR()
set(CEF_APP "${CEF_TARGET_OUT_DIR}/${CEF_TARGET}.app")
set(EXECUTABLE_NAME "${CEF_TARGET}")
set(PRODUCT_NAME "Cloakfox Chromium Prototype")
set(VERSION_SHORT "0.1.0")
add_executable(${CEF_TARGET} MACOSX_BUNDLE
  src/main_mac.mm src/browser_client.cc src/container_paths.cc src/control_channel.cc src/persona_config.cc)
SET_EXECUTABLE_TARGET_PROPERTIES(${CEF_TARGET})
target_compile_options(${CEF_TARGET} PRIVATE -fexceptions)
target_include_directories(${CEF_TARGET} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_link_libraries(${CEF_TARGET} libcef_dll_wrapper ${CEF_STANDARD_LIBS})
set_target_properties(${CEF_TARGET} PROPERTIES
  MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_SOURCE_DIR}/mac/Info.plist.in")
COPY_MAC_FRAMEWORK("${CEF_TARGET}" "${CEF_BINARY_DIR}" "${CEF_APP}")
foreach(_suffix_list ${CEF_HELPER_APP_SUFFIXES})
  string(REPLACE ":" ";" _suffix_list "${_suffix_list}")
  list(GET _suffix_list 0 _name_suffix)
  list(GET _suffix_list 1 _target_suffix)
  list(GET _suffix_list 2 _plist_suffix)
  set(_helper_target "${CEF_TARGET}_Helper${_target_suffix}")
  set(_helper_output_name "${CEF_TARGET} Helper${_name_suffix}")
  set(_helper_info_plist "${CMAKE_CURRENT_BINARY_DIR}/helper${_target_suffix}.plist")
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/mac/helper-Info.plist.in" _plist_contents)
  string(REPLACE "\${EXECUTABLE_NAME}" "${_helper_output_name}" _plist_contents "${_plist_contents}")
  string(REPLACE "\${PRODUCT_NAME}" "${_helper_output_name}" _plist_contents "${_plist_contents}")
  string(REPLACE "\${BUNDLE_ID_SUFFIX}" "${_plist_suffix}" _plist_contents "${_plist_contents}")
  file(WRITE "${_helper_info_plist}" "${_plist_contents}")
  add_executable(${_helper_target} MACOSX_BUNDLE src/process_helper_mac.cc)
  SET_EXECUTABLE_TARGET_PROPERTIES(${_helper_target})
  target_link_libraries(${_helper_target} libcef_dll_wrapper ${CEF_STANDARD_LIBS})
  set_target_properties(${_helper_target} PROPERTIES
    MACOSX_BUNDLE_INFO_PLIST "${_helper_info_plist}"
    OUTPUT_NAME "${_helper_output_name}")
  add_dependencies(${CEF_TARGET} "${_helper_target}")
  add_custom_command(TARGET ${CEF_TARGET} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
      "${CEF_TARGET_OUT_DIR}/${_helper_output_name}.app"
      "${CEF_APP}/Contents/Frameworks/${_helper_output_name}.app" VERBATIM)
endforeach()
add_custom_command(TARGET ${CEF_TARGET} POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_directory
    "${CMAKE_CURRENT_SOURCE_DIR}/THIRD_PARTY_LICENSES"
    "${CEF_APP}/Contents/Resources/THIRD_PARTY_LICENSES"
  COMMAND ${CMAKE_COMMAND} -E copy
    "${CMAKE_CURRENT_SOURCE_DIR}/cef-lock.json"
    "${CEF_APP}/Contents/Resources/cef-lock.json" VERBATIM)
enable_testing()
add_executable(container_paths_test ../../tests/engines/container_paths_test.cc src/container_paths.cc)
target_include_directories(container_paths_test PRIVATE src)
target_compile_options(container_paths_test PRIVATE -UNDEBUG)
add_test(NAME container_paths COMMAND container_paths_test)
