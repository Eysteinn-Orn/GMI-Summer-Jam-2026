extends MainMenu

const LEVEL_SELECT_SCENE := preload("res://menus/scenes/menus/level_select/level_select.tscn")

func _on_level_select_button_pressed() -> void:
	_open_sub_menu(LEVEL_SELECT_SCENE)
