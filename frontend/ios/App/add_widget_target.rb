# Wires the EEWidget lock-screen widget extension into App.xcodeproj.
# Idempotent: safe to re-run (skips everything if the target already exists).
# Run: cd frontend/ios/App && ruby add_widget_target.rb
require "xcodeproj"

PROJ = File.join(__dir__, "App.xcodeproj")
project = Xcodeproj::Project.open(PROJ)

if project.targets.any? { |t| t.name == "EEWidget" }
  puts "EEWidget target already present — nothing to do."
  exit 0
end

app = project.targets.find { |t| t.name == "App" } or abort "App target not found"

# ---- widget target ----------------------------------------------------------
widget = project.new_target(:app_extension, "EEWidget", :ios, "16.0", nil, :swift)

group = project.main_group.new_group("EEWidget", "EEWidget")
src = group.new_reference("EEWidget.swift")
group.new_reference("Info.plist")
group.new_reference("EEWidget.entitlements")
widget.source_build_phase.add_file_reference(src)

widget.build_configurations.each do |cfg|
  s = cfg.build_settings
  s["PRODUCT_BUNDLE_IDENTIFIER"] = "net.executiveenglish.app.widget"
  s["INFOPLIST_FILE"] = "EEWidget/Info.plist"
  s["GENERATE_INFOPLIST_FILE"] = "NO"
  s["CODE_SIGN_ENTITLEMENTS"] = "EEWidget/EEWidget.entitlements"
  s["CODE_SIGN_STYLE"] = "Automatic"
  s["SWIFT_VERSION"] = "5.0"
  s["IPHONEOS_DEPLOYMENT_TARGET"] = "16.0"
  s["TARGETED_DEVICE_FAMILY"] = "1,2"
  s["MARKETING_VERSION"] = "1.0"
  s["CURRENT_PROJECT_VERSION"] = "1"
  s["SKIP_INSTALL"] = "YES"
  s["ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME"] = ""
  s["LD_RUNPATH_SEARCH_PATHS"] = ["$(inherited)", "@executable_path/Frameworks", "@executable_path/../../Frameworks"]
end

# ---- app target: embed the extension + app group ----------------------------
app.add_dependency(widget)

embed = app.new_copy_files_build_phase("Embed Foundation Extensions")
embed.dst_subfolder_spec = "13" # PlugIns
bf = embed.add_file_reference(widget.product_reference)
bf.settings = { "ATTRIBUTES" => ["RemoveHeadersOnCopy"] }

app_ent = project.main_group["App"].new_reference("App.entitlements")
app.build_configurations.each do |cfg|
  cfg.build_settings["CODE_SIGN_ENTITLEMENTS"] = "App/App.entitlements"
end

project.save
puts "EEWidget target added: #{project.targets.map(&:name).join(', ')}"
