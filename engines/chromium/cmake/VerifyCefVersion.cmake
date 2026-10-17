# The upstream archive stays pinned. CEF derives its SDK minor version from the
# last assigned API version: our reviewed API15402 produces154.2.34. This exact
# native variant retains the pinned source revision and Chromium engine version.
if(NOT CEF_ROOT)
  message(FATAL_ERROR "Set CEF_ROOT to the extracted pinned CEF distribution")
endif()
file(READ "${CMAKE_CURRENT_LIST_DIR}/../cef-lock.json" _cloakfox_cef_lock)
string(JSON _cloakfox_cef_pin GET "${_cloakfox_cef_lock}" cefVersion)
file(READ "${CEF_ROOT}/include/cef_version.h" _cloakfox_cef_header)
string(REGEX MATCH "#define[ \t]+CEF_VERSION[ \t]+\"([^\"]+)\"" _cloakfox_cef_match "${_cloakfox_cef_header}")
set(_cloakfox_cef_actual "${CMAKE_MATCH_1}")
set(_cloakfox_cef_owned "154.2.34+g14c5a08+chromium-154.0.8037.98")
if(NOT "${_cloakfox_cef_actual}" STREQUAL "${_cloakfox_cef_pin}" AND
   NOT "${_cloakfox_cef_actual}" STREQUAL "${_cloakfox_cef_owned}")
  message(FATAL_ERROR "CEF version differs from cef-lock.json and reviewed native SDK variants")
endif()
if("${_cloakfox_cef_actual}" STREQUAL "${_cloakfox_cef_owned}")
  file(READ "${CEF_ROOT}/include/cef_frame.h" _cloakfox_cef_frame)
  if(NOT _cloakfox_cef_frame MATCHES "#define[ \t]+CEF_CLOAKFOX_OWNED_IME_VERSION[ \t]+1([^0-9]|$)")
    message(FATAL_ERROR "Reviewed SDK lacks its native editing contract")
  endif()
endif()
