extends MainMenu

const WORLD_25D_SCENE := "res://Scenes/world_25d.tscn"

func _on_new_game_25d_button_pressed() -> void:
	SceneLoader.load_scene(WORLD_25D_SCENE)
