extends Control

@export var title_text: String = "Outcome"
@export_multiline var subtitle_text: String = ""
@export_file("*.tscn") var retry_scene_path: String
@export_file("*.tscn") var main_menu_scene_path: String

@onready var title_label: Label = %TitleLabel
@onready var subtitle_label: Label = %SubtitleLabel
@onready var retry_button: Button = %RetryButton
@onready var menu_button: Button = %MenuButton

func _ready() -> void:
	title_label.text = title_text
	subtitle_label.text = subtitle_text

	if get_retry_scene_path().is_empty():
		retry_button.hide()
	if get_main_menu_scene_path().is_empty():
		menu_button.hide()

func get_retry_scene_path() -> String:
	if retry_scene_path.is_empty() and has_node("/root/AppConfig"):
		return AppConfig.game_scene_path
	return retry_scene_path

func get_main_menu_scene_path() -> String:
	if main_menu_scene_path.is_empty() and has_node("/root/AppConfig"):
		return AppConfig.main_menu_scene_path
	return main_menu_scene_path

func _on_retry_button_pressed() -> void:
	var path := get_retry_scene_path()
	if not path.is_empty():
		SceneLoader.load_scene(path)

func _on_menu_button_pressed() -> void:
	var path := get_main_menu_scene_path()
	if not path.is_empty():
		SceneLoader.load_scene(path)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_released("ui_cancel"):
		_on_menu_button_pressed()
