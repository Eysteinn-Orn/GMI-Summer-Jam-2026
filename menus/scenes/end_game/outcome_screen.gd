extends Control

const SUN_TEXT = [
	preload("uid://dj2uh1nmtdxte"),
	preload("uid://b6c3u515ocuep")
]
const MOON_TEXT = [
	preload("uid://cuwxuf1ty5f3l"),
	preload("uid://bq54cs15ligyt")
]
const VAMP_ANG_TEXT = [
	preload("uid://cvhkkon672x78"),
	preload("uid://dqwj52jvo4hw5")
]
const VAMP_HAP_TEXT = [
	preload("uid://exu2nk17odo"),
	preload("uid://cux5d5k3p8i4n")
]

@export var title_text: String = "Outcome"
@export_multiline var subtitle_text: String = ""
@export_file("*.tscn") var retry_scene_path: String
@export_file("*.tscn") var main_menu_scene_path: String

@onready var vampy: TextureRect = $VampyText
@onready var sun_or_moon: TextureRect = $SunORMoonText
@onready var title_label: Label = %TitleLabel
@onready var subtitle_label: Label = %SubtitleLabel
@onready var retry_button: Button = %RetryButton
@onready var menu_button: Button = %MenuButton
var sprite_timer : float = 0.0
var is_sprite_2  : bool  = false

func _ready() -> void:
	title_label.text = title_text
	subtitle_label.text = subtitle_text

	if get_retry_scene_path().is_empty():
		retry_button.hide()
	if get_main_menu_scene_path().is_empty():
		menu_button.hide()
	if title_text == "GAME OVER":
		SFX.destroy_sounds("vamp_dead")
		SFX.create_sound("vamp_dead", -4.0)
	else:
		SFX.destroy_sounds("motif")
		SFX.create_sound("motif",0,0,true)

func _process(delta: float) -> void:
	sprite_timer += delta
	if sprite_timer >= 0.5:
		if is_sprite_2:
			if title_text == "GAME OVER":
				vampy.texture = VAMP_ANG_TEXT[0]
				sun_or_moon.texture = SUN_TEXT[0]
			else:
				vampy.texture = VAMP_HAP_TEXT[0]
				sun_or_moon.texture = MOON_TEXT[0]
			is_sprite_2 = false
		else:
			if title_text == "GAME OVER":
				vampy.texture = VAMP_ANG_TEXT[1]
				sun_or_moon.texture = SUN_TEXT[1]
			else:
				vampy.texture = VAMP_HAP_TEXT[1]
				sun_or_moon.texture = MOON_TEXT[1]
			is_sprite_2 = true
		sprite_timer = 0.0

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
