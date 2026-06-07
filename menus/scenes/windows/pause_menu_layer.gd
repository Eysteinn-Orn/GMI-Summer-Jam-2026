extends CanvasLayer

@onready var pause_menu = %PauseMenu

func _on_pause_menu_hidden():
	hide()

func _on_visibility_changed():
	if visible:
		pause_menu.show()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and not visible and _can_pause_here():
		show()
		get_viewport().set_input_as_handled()

func _can_pause_here() -> bool:
	var current := get_tree().current_scene
	if current == null:
		return false
	var path := current.scene_file_path
	if path == AppConfig.main_menu_scene_path:
		return false
	if path.begins_with("res://menus/scenes/opening/") or path.begins_with("res://menus/scenes/loading_screen/"):
		return false
	if current is MainMenu:
		return false
	return true

func _ready():
	visible = false
	visibility_changed.connect(_on_visibility_changed)
