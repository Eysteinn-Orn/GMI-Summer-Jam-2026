extends Control

const LEVELS := {
	"Grass": "res://Scenes/world.tscn",
	"Town": "res://Scenes/world_town.tscn",
	"2.5D World": "res://Scenes/world_25d.tscn",
	"2.5D Town": "res://Scenes/world_25d_town.tscn",
}

func _ready() -> void:
	for level_name in LEVELS:
		var button := Button.new()
		button.text = level_name
		button.pressed.connect(_on_level_pressed.bind(LEVELS[level_name]))
		%LevelButtons.add_child(button)

func _on_level_pressed(scene_path: String) -> void:
	SceneLoader.load_scene(scene_path)

func _input(event: InputEvent) -> void:
	if event.is_action_released("ui_cancel"):
		hide()
