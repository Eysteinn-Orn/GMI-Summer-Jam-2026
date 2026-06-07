extends CanvasLayer

const HEALTH_TEXTURES : Array[CompressedTexture2D] = [
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_0.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_1.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_2.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_3.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_4.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_5.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_6.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_7.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_8.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_9.png"),
	preload("res://Assets/10k Game Assets/Pixel Art (4770)/8bit Adventure (1489)/UI (12)/ui_healthbar_10.png"),
] 
const MOON_TEXTURES : Array[CompressedTexture2D] = [
	preload("uid://v64fymjl8ak"),
	preload("uid://b0hamnh7lrp8l"),
	preload("uid://bb1jlr3kqse0d"),
	preload("uid://cuwxuf1ty5f3l"),
	preload("uid://bq54cs15ligyt")
]
const SUN_TEXTURES : Array[CompressedTexture2D] = [
	preload("uid://dsrls151do1wh"),
	preload("uid://hx4kn6pjfb4u"),
	preload("uid://b81ibcss1u6hs"),
	preload("uid://b6c3u515ocuep"),
	preload("uid://dj2uh1nmtdxte"),
	preload("uid://c84kqkecy0rmb"),
	preload("uid://b8gjendjdnbxu"),
	preload("uid://f1dyhmhc6wcg")
]

const SHADOW_START : float = 50
const SHADOW_END   : float = 10
const SHADOW_DIF   : float = SHADOW_END - SHADOW_START
const MOON_START : Vector2 = Vector2(1746.0, 906.0)
const MOON_END   : Vector2 = Vector2(1628.0, 906.0)
const MOON_DIF   : Vector2 = MOON_END - MOON_START
const ECLIPSE_CLR_START : Color = Color(0.071, 0.0, 0.272, 1.0)
const ECLIPSE_CLR_END   : Color = Color(0.717, 0.511, 0.247, 1.0)
const ECLIPSE_CLR_DIF   : Color = ECLIPSE_CLR_END - ECLIPSE_CLR_START
const LVL_TIME : int = 90

@export var moon : Node2D
@onready var background: TextureRect = $Background
@onready var health_bar: TextureRect = $HealthBar
@onready var vamp_icon: TextureRect = $VampIcon
@onready var sun_icon: TextureRect = $SunIcon
@onready var moon_icon: TextureRect = $MoonIcon
@onready var level_time: Label = $LevelTime

var hb_wobble      : bool  = false
var hb_wobble_time : float = 0.0
var lvl_progress   : float = 0.0
var lvl_time       : float = LVL_TIME

func sec_to_str(sec : int) -> String:
	var minutes : int = floor(float(sec) / 60.0)
	var sec_left : int = sec - minutes * 60
	var min_str = str(minutes)
	var sec_str = str(sec_left)
	if sec_str.length() < 2: sec_str = "0" + sec_str
	return min_str + ":" + sec_str

func update_health_bar(health : int):
	health_bar.rotation = 0
	hb_wobble = true
	hb_wobble_time = 0.0
	health_bar.texture = HEALTH_TEXTURES[health]

func _process(delta: float) -> void:
	lvl_time -= delta
	lvl_progress += delta / LVL_TIME
	if lvl_progress >= 1:
		level_time.text = "GAME OVER"
		return
	level_time.text = sec_to_str(ceil(lvl_time))
	moon_icon.position = MOON_START + MOON_DIF * lvl_progress
	moon.shadow_shape.shape.radius = SHADOW_START + (SHADOW_DIF * lvl_progress)
	moon_icon.scale = Vector2(1 - (lvl_progress / 4), 1 - (lvl_progress / 4))
	if hb_wobble == true:
		hb_wobble_time += delta
		health_bar.rotation = 0.05 * sin(hb_wobble_time * (100 - 75 * hb_wobble_time))
		if hb_wobble_time > 0.5:
			health_bar.rotation = 0
			hb_wobble = false
	background.texture.gradient.colors[2] = (
		ECLIPSE_CLR_START + ECLIPSE_CLR_DIF * lvl_progress
	)
	moon_icon.texture = MOON_TEXTURES[floor(5 - lvl_progress * 5)]
	sun_icon.texture = SUN_TEXTURES[floor(8 - lvl_progress * 8)]
