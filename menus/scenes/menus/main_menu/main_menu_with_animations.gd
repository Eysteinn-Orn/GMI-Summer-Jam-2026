extends MainMenu
## Main menu extension that animates the title and menu fading in.
## The animation can be skipped by the player with any input.

var animation_state_machine : AnimationNodeStateMachinePlayback

func intro_done() -> void:
	animation_state_machine.travel("OpenMainMenu")

func check_cutscene() -> void:
	if !SFX.intro_done: _on_eclipse_anim_button_pressed()

func _is_in_intro() -> bool:
	return animation_state_machine.get_current_node() == "Intro"

func _event_skips_intro(event : InputEvent) -> bool:
	return event.is_action_released("ui_accept") or \
		event.is_action_released("ui_select") or \
		event.is_action_released("ui_cancel") or \
		_event_is_mouse_button_released(event)

func _open_sub_menu(menu : PackedScene) -> Node:
	animation_state_machine.travel("OpenSubMenu")
	return super._open_sub_menu(menu)

func _close_sub_menu() -> void:
	super._close_sub_menu()
	animation_state_machine.travel("OpenMainMenu")

func _input(event : InputEvent) -> void:
	if _is_in_intro() and _event_skips_intro(event):
		intro_done()
		return
	super._input(event)

func _on_level_select_button_pressed() -> void:
	_open_sub_menu(preload("res://menus/scenes/menus/level_select/level_select.tscn"))

func _on_eclipse_anim_button_pressed() -> void:
	_open_sub_menu(preload("res://menus/scenes/menus/main_menu/eclipse_anim.tscn"))

func _ready() -> void:
	super._ready()
	animation_state_machine = $MenuAnimationTree.get("parameters/playback")
	if !SFX.intro_done:
		_open_sub_menu(preload("res://menus/scenes/menus/main_menu/eclipse_anim.tscn"))

func _exit_tree() -> void:
	SFX.destroy_sounds("intro")
