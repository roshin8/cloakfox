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
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/VerifyCefVersion.cmake")
add_subdirectory("${CEF_LIBCEF_DLL_WRAPPER_PATH}" libcef_dll_wrapper)
set(CEF_TARGET CloakfoxChromium)
SET_CEF_TARGET_OUT_DIR()
set(CEF_APP "${CEF_TARGET_OUT_DIR}/${CEF_TARGET}.app")
set(EXECUTABLE_NAME "${CEF_TARGET}")
set(PRODUCT_NAME "Cloakfox Chromium Prototype")
set(VERSION_SHORT "0.1.0")
# One schema registry is consumed by the reference policy and native adapter.
# Listed versions are requirements, never a claim that a group is implemented.
set(_policy_contract "${CMAKE_CURRENT_SOURCE_DIR}/../shared/privacy_contract.json")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_policy_contract}")
file(READ "${_policy_contract}" _policy_json)
string(JSON _policy_schema GET "${_policy_json}" schemaVersion)
string(JSON _policy_group_count LENGTH "${_policy_json}" groupVersions)
math(EXPR _policy_group_last "${_policy_group_count} - 1")
set(_policy_group_names "")
foreach(_index RANGE 0 ${_policy_group_last})
  string(JSON _group MEMBER "${_policy_json}" groupVersions ${_index})
  if(NOT _group MATCHES "^[A-Za-z]+$")
    message(FATAL_ERROR "Invalid engine policy group")
  endif()
  string(APPEND _policy_group_names "  \"${_group}\",\n")
endforeach()
configure_file(src/policy_contract.h.in generated/policy_contract.h @ONLY)
add_executable(${CEF_TARGET} MACOSX_BUNDLE
  src/main_mac.mm src/offscreen_client.cc src/browser_client.cc src/container_paths.cc src/control_channel.cc src/persona_config.cc
  ../../additions/cloakcfg/engine-host/surface_transport_mac.mm ../../additions/cloakcfg/engine-host/surface_launch_mac.mm)
SET_EXECUTABLE_TARGET_PROPERTIES(${CEF_TARGET})
target_compile_options(${CEF_TARGET} PRIVATE -fexceptions)
target_include_directories(${CEF_TARGET} PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated")
target_include_directories(${CEF_TARGET} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src" "${CMAKE_CURRENT_SOURCE_DIR}/../../additions/cloakcfg/engine-host")
target_link_libraries(${CEF_TARGET} libcef_dll_wrapper ${CEF_STANDARD_LIBS} "-framework IOSurface" bsm)
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
target_include_directories(container_paths_test PRIVATE src ../../additions/cloakcfg/engine-host)
target_compile_options(container_paths_test PRIVATE -UNDEBUG)
add_test(NAME container_paths COMMAND container_paths_test)
add_executable(surface_transport_test ../../tests/engines/surface_transport_test.mm ../../additions/cloakcfg/engine-host/surface_transport_mac.mm ../../additions/cloakcfg/engine-host/surface_launch_mac.mm)
target_include_directories(surface_transport_test PRIVATE src ../../additions/cloakcfg/engine-host)
target_compile_options(surface_transport_test PRIVATE -UNDEBUG -Wall -Wextra -Werror)
target_link_libraries(surface_transport_test "-framework Foundation" "-framework IOSurface" bsm)
add_test(NAME surface_transport COMMAND surface_transport_test)
set_tests_properties(surface_transport PROPERTIES TIMEOUT 30)
add_executable(host_surface_probe ../../tests/engines/host_surface_probe.mm ../../additions/cloakcfg/engine-host/surface_transport_mac.mm ../../additions/cloakcfg/engine-host/surface_launch_mac.mm)
target_include_directories(host_surface_probe PRIVATE src ../../additions/cloakcfg ../../additions/cloakcfg/engine-host)
target_compile_options(host_surface_probe PRIVATE -UNDEBUG -Wall -Wextra -Werror)
target_link_libraries(host_surface_probe "-framework Foundation" "-framework IOSurface" bsm)

# The shared boundary must remain usable in Gecko's no-exceptions build.
set_source_files_properties(
  ../../additions/cloakcfg/engine-host/surface_launch_mac.mm
  ../../additions/cloakcfg/engine-host/surface_transport_mac.mm
  PROPERTIES COMPILE_OPTIONS "-fno-exceptions")
