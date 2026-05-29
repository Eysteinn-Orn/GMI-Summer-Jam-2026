@tool
extends EditorPlugin

## Adds "Pixel Editor" to the editor's Project > Tools menu, which launches the
## standalone Python pixel editor (tools/pixel_editor.py) as a separate process.

const MENU_ITEM := "Pixel Editor"
const SCRIPT_PATH := "res://tools/pixel_editor.py"

func _enter_tree() -> void:
	add_tool_menu_item(MENU_ITEM, _launch)

func _exit_tree() -> void:
	remove_tool_menu_item(MENU_ITEM)

func _launch() -> void:
	var script_abs := ProjectSettings.globalize_path(SCRIPT_PATH)
	# python3 on macOS/Linux, "python" as a fallback (typical on Windows).
	for python in ["python3", "python"]:
		if OS.create_process(python, [script_abs]) > 0:
			return
	push_error("Pixel Editor: could not start Python. Is python3 installed and on PATH?")
