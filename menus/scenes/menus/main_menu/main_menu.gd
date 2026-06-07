extends MainMenu

const LEVEL_SELECT_SCENE := preload("res://menus/scenes/menus/level_select/level_select.tscn")
const ECLIPSE_ANIM_SCENE := preload("res://menus/scenes/menus/main_menu/eclipse_anim.tscn")

func _on_level_select_button_pressed() -> void:
	_open_sub_menu(LEVEL_SELECT_SCENE)

func _on_eclipse_anim_button_pressed() -> void:
	_open_sub_menu(ECLIPSE_ANIM_SCENE)
