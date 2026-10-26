#include "persona_config.h"
#include "container_paths.h"
#include <set>
#include <stdexcept>

namespace cloakfox {
namespace {
void exactFields(CefRefPtr<CefDictionaryValue> value,
                 const std::set<std::string>& expected) {
  if (!value) throw std::runtime_error("Invalid config object");
  CefDictionaryValue::KeyList keys;
  value->GetKeys(keys);
  std::set<std::string> actual;
  for (const auto& key : keys) actual.insert(key.ToString());
  if (actual != expected) throw std::runtime_error("Unsupported config fields");
}
void optionFields(CefRefPtr<CefDictionaryValue> value, bool complete, bool presentation) {
  if (!value || (complete && (!value->HasKey("canvas") || !value->HasKey("blockWebGPUReadback"))))
    throw std::runtime_error("Missing config options");
  CefDictionaryValue::KeyList keys; value->GetKeys(keys);
  for (const auto& key : keys) {
    if (!complete && key == "presentation" && presentation && value->GetType(key) == VTYPE_DICTIONARY) continue;
    if (((key != "canvas" && key != "blockWebGPUReadback") &&
         !(presentation && (key == "navigator" || key == "language" || key == "timezone" ||
                            key == "display"))) ||
        value->GetType(key) != VTYPE_BOOL)
      throw std::runtime_error("Unsupported config option");
  }
}
void validatePresentation(CefRefPtr<CefDictionaryValue> value) {
  const std::set<std::string> base{"hardwareConcurrency", "deviceMemory", "languages", "timezone"};
  const std::set<std::string> display{"screenWidth", "screenHeight", "screenAvailWidth", "screenAvailHeight"};
  if (!value) throw std::runtime_error("Invalid identity presentation");
  CefDictionaryValue::KeyList keys; value->GetKeys(keys);
  std::set<std::string> present;
  for (const auto& key : keys) present.insert(key.ToString());
  for (const auto& key : base)
    if (!present.count(key)) throw std::runtime_error("Unsupported presentation fields");
  bool any_display = false, all_display = true;
  for (const auto& key : present) {
    if (base.count(key)) continue;
    if (!display.count(key)) throw std::runtime_error("Unsupported presentation fields");
  }
  for (const auto& key : display) {
    if (present.count(key)) any_display = true;
    else all_display = false;
  }
  if (any_display && !all_display) throw std::runtime_error("Incomplete display presentation");
  if (value->GetType("hardwareConcurrency") != VTYPE_INT ||
      (value->GetInt("hardwareConcurrency") < 1 || value->GetInt("hardwareConcurrency") > 128) ||
      value->GetType("deviceMemory") != VTYPE_INT ||
      !std::set<int>{4,8}.count(value->GetInt("deviceMemory")) ||
      value->GetType("languages") != VTYPE_LIST || value->GetType("timezone") != VTYPE_STRING)
    throw std::runtime_error("Invalid identity presentation");
  auto languages = value->GetList("languages");
  // Structure only. The engine's own ICU data decides which languages and
  // zones it can render; the framework refuses a persona it cannot render when
  // the container context is created, before any renderer exists, because
  // Blink aborts a renderer whose language or zone ICU cannot adopt. This gate
  // keeps the host boundary safe and never builds a presentation from a broken
  // list.
  if (languages->GetSize() < 1 || languages->GetSize() > 4)
    throw std::runtime_error("Unsupported language list");
  std::set<std::string> seen;
  for (size_t index = 0; index < languages->GetSize(); ++index) {
    if (languages->GetType(index) != VTYPE_STRING)
      throw std::runtime_error("Unsupported language list");
    const auto tag = languages->GetString(index).ToString();
    if (tag.empty() || tag.size() > 128 || !seen.insert(tag).second)
      throw std::runtime_error("Unsupported language list");
  }
  const auto timezone = value->GetString("timezone").ToString();
  if (timezone.empty() || timezone.size() > 64)
    throw std::runtime_error("Unsupported timezone");
  if (all_display) {
    const int width = value->GetInt("screenWidth"), height = value->GetInt("screenHeight");
    const int avail_width = value->GetInt("screenAvailWidth"), avail_height = value->GetInt("screenAvailHeight");
    if (value->GetType("screenWidth") != VTYPE_INT || value->GetType("screenHeight") != VTYPE_INT ||
        value->GetType("screenAvailWidth") != VTYPE_INT || value->GetType("screenAvailHeight") != VTYPE_INT ||
        width < 1 || width > 16384 || height < 1 || height > 16384 ||
        avail_width < 1 || avail_width > width || avail_height < 1 || avail_height > height)
      throw std::runtime_error("Invalid display geometry");
  }
}
}
PersonaConfig parsePersonaConfig(CefRefPtr<CefDictionaryValue> value,
                                int canvasVersion, int webgpuVersion, int identityVersion,
                                int displayVersion) {
  exactFields(value, {"schemaVersion", "engine", "containerId", "private", "revision", "enabled", "persona"});
  if (value->GetType("schemaVersion") != VTYPE_INT || value->GetInt("schemaVersion") != 1 ||
      value->GetType("revision") != VTYPE_INT || value->GetInt("revision") < 1 ||
      value->GetType("engine") != VTYPE_STRING || value->GetString("engine") != "chromium" ||
      value->GetType("containerId") != VTYPE_STRING ||
      !isValidContainerId(value->GetString("containerId").ToString()) ||
      value->GetType("private") != VTYPE_BOOL || value->GetType("enabled") != VTYPE_BOOL ||
      value->GetType("persona") != VTYPE_DICTIONARY)
    throw std::runtime_error("Invalid config schema, engine or ownership");
  auto persona = value->GetDictionary("persona");
  const bool hasPresentation = persona->HasKey("presentation");
  auto personaFields = std::set<std::string>{"seed", "options", "overrides"};
  if (hasPresentation) personaFields.insert("presentation");
  exactFields(persona, personaFields);
  if (persona->GetType("seed") != VTYPE_STRING ||
      persona->GetType("options") != VTYPE_DICTIONARY || persona->GetType("overrides") != VTYPE_DICTIONARY)
    throw std::runtime_error("Invalid persona config");
  const auto seed = persona->GetString("seed").ToString();
  if (seed.size() != 64 || seed.find_first_not_of("0123456789abcdef") != std::string::npos)
    throw std::runtime_error("Invalid persona seed");
  auto options = persona->GetDictionary("options");
  auto overrides = persona->GetDictionary("overrides");
  optionFields(options, true, hasPresentation); optionFields(overrides, false, hasPresentation);
  if (hasPresentation) {
    if (identityVersion != 1 && identityVersion != 2) throw std::runtime_error("Backend does not support native identity presentation");
    if (persona->GetType("presentation") != VTYPE_DICTIONARY) throw std::runtime_error("Invalid presentation");
    validatePresentation(persona->GetDictionary("presentation"));
    // The display block rides on the identity presentation; a framework built
    // without the display hook must never silently ignore it.
    if (persona->GetDictionary("presentation")->HasKey("screenWidth") && displayVersion != 1)
      throw std::runtime_error("Backend does not support native display privacy");
    if (identityVersion < 2 && !std::set<int>{4,8,16}.count(
            persona->GetDictionary("presentation")->GetInt("hardwareConcurrency")))
      throw std::runtime_error("Backend does not support this BrowserForge processor count");
    if (overrides->HasKey("presentation")) {
      validatePresentation(overrides->GetDictionary("presentation"));
      if (!overrides->GetDictionary("presentation")->IsEqual(persona->GetDictionary("presentation")))
        throw std::runtime_error("Presentation override is not applied");
    }
  }
  // v1 requires both current hooks, even when disabled. Never acknowledge an
  // unsupported option as implemented by an unpatched/older binary SDK.
  if (canvasVersion != 1 || webgpuVersion != 1)
    throw std::runtime_error("Backend does not support persona options");
  const auto effective = [&options, &overrides](const char* key) {
    return overrides->HasKey(key) ? overrides->GetBool(key) :
           options->HasKey(key) ? options->GetBool(key) : true;
  };
  const bool enabled = value->GetBool("enabled");
  CefRefPtr<CefDictionaryValue> presentation;
  if (hasPresentation) {
    const auto source = persona->GetDictionary("presentation");
    presentation = CefDictionaryValue::Create();
    for (const auto* key : {"navigator", "language", "timezone"})
      presentation->SetBool(key, enabled && effective(key));
    presentation->SetInt("hardwareConcurrency", source->GetInt("hardwareConcurrency"));
    presentation->SetInt("deviceMemory", source->GetInt("deviceMemory"));
    auto languages = source->GetList("languages");
    presentation->SetString("locale", languages->GetString(0));
    std::string joined = languages->GetString(0).ToString();
    for (size_t index = 1; index < languages->GetSize(); ++index)
      joined += "," + languages->GetString(index).ToString();
    presentation->SetString("languages", joined);
    presentation->SetString("timezoneId", source->GetString("timezone"));
    // Owner-provided screen geometry; applied only when the identity and the
    // display option are active.
    if (enabled && effective("display") && source->HasKey("screenWidth"))
      for (const auto* key : {"screenWidth", "screenHeight", "screenAvailWidth", "screenAvailHeight"})
        presentation->SetInt(key, source->GetInt(key));
  }
  return {value->Copy(false), value->GetString("containerId").ToString(), seed,
          value->GetInt("revision"), value->GetBool("private"),
          enabled && effective("canvas"), enabled && effective("blockWebGPUReadback"), presentation};
}
}
