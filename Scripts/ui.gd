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
const MOON_START : Vector2 = Vector2(20.0, 906.0)
const MOON_END   : Vector2 = Vector2(146.0, 906.0)
const MOON_DIF   : Vector2 = MOON_END - MOON_START
const ECLIPSE_CLR_START : Color = Color(0.071, 0.0, 0.272, 1.0)
const ECLIPSE_CLR_END   : Color = Color(0.717, 0.511, 0.247, 1.0)
const ECLIPSE_CLR_DIF   : Color = ECLIPSE_CLR_END - ECLIPSE_CLR_START
const LVL_TIME : int = 90

@export var moon : Node2D
@onready var background: TextureRect = $Background
@onready var health_bar: TextureRect = $HealthBar
@onready var vamp_icon: Sprite2D = $VampIcon
@onready var sun_icon: TextureRect = $SunIcon
@onready var moon_icon: TextureRect = $MoonIcon
@onready var level_time: Label = $LevelTime
@onready var keys_progress: Label = get_node_or_null("KeysProgress")

var hb_wobble      : bool  = false
var hb_wobble_time : float = 0.0
var lvl_progress   : float = 0.0
var lvl_time       : float = LVL_TIME
var total_level_time: float = LVL_TIME

func _ready() -> void:
	update_time_state(LVL_TIME, LVL_TIME)
	set_keys_progress(0, 4)

func sec_to_str(sec : int) -> String:
	var minutes : int = floor(float(sec) / 60.0)
	var sec_left : int = sec - minutes * 60
	var min_str = str(minutes)
	var sec_str = str(sec_left)
	if sec_str.length() < 2: sec_str = "0" + sec_str
	return min_str + ":" + sec_str

func update_health_bar(health : int):
	if not health_bar:
		return
	health_bar.rotation = 0
	hb_wobble = true
	hb_wobble_time = 0.0
	health_bar.texture = HEALTH_TEXTURES[health]

func _process(delta: float) -> void:
	if not health_bar:
		return
	if hb_wobble == true:
		hb_wobble_time += delta
		health_bar.rotation = 0.05 * sin(hb_wobble_time * (100 - 75 * hb_wobble_time))
		if hb_wobble_time > 0.5:
			health_bar.rotation = 0
			hb_wobble = false

func update_time_state(time_left: float, total_time: float) -> void:
	total_level_time = maxf(total_time, 0.001)
	lvl_time = clampf(time_left, 0.0, total_level_time)
	lvl_progress = clampf(1.0 - (lvl_time / total_level_time), 0.0, 1.0)
	_apply_time_visuals()

func set_keys_progress(collected: int, required: int) -> void:
	if keys_progress:
		keys_progress.text = "Keys: %d/%d" % [collected, required]

func show_end_state(text: String) -> void:
	if not level_time:
		return
	level_time.position.x = 600
	level_time.text = text

func _apply_time_visuals() -> void:
	if not level_time or not moon_icon or not sun_icon or not background:
		return
	if not background.texture or not background.texture.gradient:
		return
	level_time.text = sec_to_str(int(ceil(lvl_time)))
	moon_icon.position = MOON_START + MOON_DIF * lvl_progress
	level_time.position.x = moon_icon.position.x
	if moon and moon.shadow_shape and moon.shadow_shape.shape:
		moon.shadow_shape.shape.radius = SHADOW_START + (SHADOW_DIF * lvl_progress)
	moon_icon.scale = Vector2(1 - (lvl_progress / 4), 1 - (lvl_progress / 4))
	background.texture.gradient.colors[2] = (
		ECLIPSE_CLR_START + ECLIPSE_CLR_DIF * lvl_progress
	)
	var moon_index := clampi(int(floor(4 - lvl_progress * 4)), 0, MOON_TEXTURES.size() - 1)
	var sun_index := clampi(int(floor(7 - lvl_progress * 7)), 0, SUN_TEXTURES.size() - 1)
	moon_icon.texture = MOON_TEXTURES[moon_index]
	sun_icon.texture = SUN_TEXTURES[sun_index]

func update_vamp(stepping : bool = false):
	if not vamp_icon:
		return
	if stepping:
		if vamp_icon.frame >= 5:
			vamp_icon.frame = 0
		else: vamp_icon.frame += 1
	else: vamp_icon.frame = 6
