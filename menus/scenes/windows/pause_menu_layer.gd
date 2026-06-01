extends CanvasLayer

@onready var pause_menu = %PauseMenu

func _on_pause_menu_hidden():
	hide()

func _on_visibility_changed():
	if visible:
		pause_menu.show()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and not visible:
		show()
		get_viewport().set_input_as_handled()

func _ready():
	visible = false
	visibility_changed.connect(_on_visibility_changed)
