extends Control

const LEVELS := {
	"The Graveyard": "res://Scenes/world.tscn",
}

func _ready() -> void:
	for level_name in LEVELS:
		var button := Button.new()
		button.text = level_name
		button.theme = load("res://Assets/themes/main.tres")
		button.pressed.connect(_on_level_pressed.bind(LEVELS[level_name]))
		%LevelButtons.add_child(button)

func _on_level_pressed(scene_path: String) -> void:
	SceneLoader.load_scene(scene_path)

func _input(event: InputEvent) -> void:
	if event.is_action_released("ui_cancel"):
		hide()
