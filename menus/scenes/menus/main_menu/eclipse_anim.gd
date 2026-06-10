extends Control

const SUN_BASE_PATHS := [
	"res://Assets/sprites/eclipse/Sun_Base01.png",
	"res://Assets/sprites/eclipse/Sun_Base02.png",
	"res://Assets/sprites/eclipse/Sun_Base03.png",
]
const SUN_RAGE_PATHS := [
	"res://Assets/sprites/eclipse/Sun_Rage01.png",
	"res://Assets/sprites/eclipse/Sun_Rage02.png",
	"res://Assets/sprites/eclipse/Sun_Rage03.png",
	"res://Assets/sprites/eclipse/Sun_Rage04.png",
	"res://Assets/sprites/eclipse/Sun_Rage05.png",
]
const MOON_PATHS := [
	"res://Assets/sprites/eclipse/MoonRenderTest01_F01.png",
	"res://Assets/sprites/eclipse/MoonRenderTest01_F02.png",
	"res://Assets/sprites/eclipse/MoonRenderTest01_F03.png",
	"res://Assets/sprites/eclipse/MoonRenderTest01_F04.png",
	"res://Assets/sprites/eclipse/MoonRenderTest01_F05.png",
]
const VAMP_PATHS := [
	"res://Assets/sprites/vampire/Vamp_64_V01.png",
	"res://Assets/sprites/vampire/Vamp_64_V02.png",
	"res://Assets/sprites/vampire/Vamp_64_V03.png",
	"res://Assets/sprites/vampire/Vamp_64_V04.png",
	"res://Assets/sprites/vampire/Vamp_64_V05.png",
	"res://Assets/sprites/vampire/Vamp_64_V06.png",
	"res://Assets/sprites/vampire/Vamp_64_V07.png",
	"res://Assets/sprites/vampire/Vamp_64_V08.png",
]
const AWAKENING_BG_PATH := "res://Assets/sprites/eclipse/awakening_bg.png"

const MOTION_BLUR_SHADER := "
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float strength = 0.0;
void fragment() {
	vec4 col = vec4(0.0);
	for (int i = 0; i < 12; i++) {
		float t = float(i) / 11.0 - 0.5;
		col += texture(screen_tex, SCREEN_UV + vec2(0.0, t * strength));
	}
	COLOR = col / 12.0;
}
"

const VIEW_W := 1920.0
const VIEW_H := 1080.0
const SUN_POS := Vector2(1280, 520)
const SUN_SCALE := 2.0
const MOON_SCALE := 1.8
const MOON_Y := 526.0
const MOON_START := Vector2(-400, MOON_Y)
const MOON_END := Vector2(SUN_POS.x, MOON_Y)
const SKY_DAY := Color(0.45, 0.72, 0.95)
const SKY_ECLIPSED := Color(0.02, 0.02, 0.08)

# Awakening view: bg scaled to cover the viewport, vampire by the temple door
const BG_SCALE := VIEW_W / 424.0
const VAMP_POS := Vector2(1160, 820)
const VAMP_SCALE := 3.0

var _world: Control
var _sun: Sprite2D
var _moon: Sprite2D
var _vamp: Sprite2D
var _sun_frames: Array[Texture2D] = []
var _moon_frames: Array[Texture2D] = []
var _vamp_frames: Array[Texture2D] = []
var _sun_raging := false
var _sun_frame_time := 0.18
var _moon_frame_time := 0.32
var _vamp_frame_time := 0.15
var _moon_locked := false
var _sun_acc := 0.0
var _moon_acc := 0.0
var _vamp_acc := 0.0
var _sun_idx := 0
var _moon_idx := 0
var _vamp_idx := 0

var _sun_bubble: Control
var _moon_bubble: Control
var _vamp_bubble: Control
var _sky: ColorRect
var _blur_mat: ShaderMaterial

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	_world = Control.new()
	_world.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_world)

	_sky = ColorRect.new()
	_sky.color = SKY_DAY
	_sky.size = Vector2(VIEW_W, VIEW_H)
	_sky.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_world.add_child(_sky)

	for p in SUN_BASE_PATHS:
		_sun_frames.append(load(p))
	for p in MOON_PATHS:
		_moon_frames.append(load(p))
	for p in VAMP_PATHS:
		_vamp_frames.append(load(p))

	_sun = Sprite2D.new()
	_sun.texture = _sun_frames[0]
	_sun.position = SUN_POS
	_sun.scale = Vector2(SUN_SCALE, SUN_SCALE)
	_world.add_child(_sun)

	_moon = Sprite2D.new()
	_moon.texture = _moon_frames[0]
	_moon.position = MOON_START
	_moon.scale = Vector2(MOON_SCALE, MOON_SCALE)
	_world.add_child(_moon)

	# Awakening view, one screen below the eclipse view
	var bg := Sprite2D.new()
	bg.texture = load(AWAKENING_BG_PATH)
	bg.centered = false
	bg.position = Vector2(0, VIEW_H)
	bg.scale = Vector2(BG_SCALE, BG_SCALE)
	_world.add_child(bg)

	_vamp = Sprite2D.new()
	_vamp.texture = _vamp_frames[0]
	_vamp.position = Vector2(VAMP_POS.x, VIEW_H + VAMP_POS.y)
	_vamp.scale = Vector2(VAMP_SCALE, VAMP_SCALE)
	_world.add_child(_vamp)

	_sun_bubble = _make_bubble(Color(1, 1, 0.85), Color.BLACK)
	_world.add_child(_sun_bubble)
	_sun_bubble.visible = false

	_moon_bubble = _make_bubble(Color(0.85, 0.9, 1.0), Color.BLACK)
	_world.add_child(_moon_bubble)
	_moon_bubble.visible = false

	_vamp_bubble = _make_bubble(Color(0.18, 0.1, 0.25), Color(0.95, 0.9, 1.0))
	_world.add_child(_vamp_bubble)
	_vamp_bubble.visible = false

	_blur_mat = ShaderMaterial.new()
	var sh := Shader.new()
	sh.code = MOTION_BLUR_SHADER
	_blur_mat.shader = sh
	_blur_mat.set_shader_parameter("strength", 0.0)
	var blur := ColorRect.new()
	blur.material = _blur_mat
	blur.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	blur.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(blur)

	var back := Button.new()
	back.text = "Skip"
	back.position = Vector2(24, 24)
	back.custom_minimum_size = Vector2(120, 40)
	back.pressed.connect(_on_back_pressed)
	add_child(back)

	_run_sequence()

func _make_bubble(bg_color: Color, text_color: Color) -> Control:
	var panel := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg_color
	sb.set_corner_radius_all(20)
	sb.set_border_width_all(4)
	sb.border_color = Color.BLACK
	sb.content_margin_left = 18
	sb.content_margin_right = 18
	sb.content_margin_top = 12
	sb.content_margin_bottom = 12
	panel.add_theme_stylebox_override("panel", sb)

	var label := Label.new()
	label.name = "Text"
	label.add_theme_color_override("font_color", text_color)
	label.add_theme_font_size_override("font_size", 28)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size = Vector2(360, 0)
	panel.add_child(label)
	return panel

func _say(bubble: Control, anchor: Vector2, text: String, duration: float) -> void:
	var label: Label = bubble.get_node("Text")
	label.text = text
	bubble.visible = true
	bubble.reset_size()
	await get_tree().process_frame
	var bub_size := bubble.size
	bubble.position = anchor - Vector2(bub_size.x * 0.5, bub_size.y + 40)
	await get_tree().create_timer(duration).timeout
	bubble.visible = false

func _process(delta: float) -> void:
	_sun_acc += delta
	if _sun_acc >= _sun_frame_time:
		_sun_acc = 0.0
		_sun_idx = (_sun_idx + 1) % _sun_frames.size()
		_sun.texture = _sun_frames[_sun_idx]

	if not _moon_locked:
		_moon_acc += delta
		if _moon_acc >= _moon_frame_time:
			_moon_acc = 0.0
			_moon_idx = (_moon_idx + 1) % _moon_frames.size()
			_moon.texture = _moon_frames[_moon_idx]

	_vamp_acc += delta
	if _vamp_acc >= _vamp_frame_time:
		_vamp_acc = 0.0
		_vamp_idx = (_vamp_idx + 1) % _vamp_frames.size()
		_vamp.texture = _vamp_frames[_vamp_idx]

func _enter_rage() -> void:
	if _sun_raging:
		return
	_sun_raging = true
	_sun_frames.clear()
	for p in SUN_RAGE_PATHS:
		_sun_frames.append(load(p))
	_sun_idx = 0
	_sun_frame_time = 0.1

func _move_moon_to(target: Vector2, duration: float) -> void:
	var tw := create_tween()
	tw.tween_property(_moon, "position", target, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tw.finished

func _run_sequence() -> void:
	await _say(_sun_bubble, _sun.position + Vector2(0, -180), "Another glorious day of shining!", 2.2)
	await _say(_sun_bubble, _sun.position + Vector2(0, -180), "Nobody can dim MY light!", 2.0)

	_move_moon_to(Vector2(700, MOON_Y), 2.5)
	await _say(_moon_bubble, _moon.position + Vector2(0, -180), "Oh hi sun...", 1.8)
	await get_tree().create_timer(0.6).timeout

	_move_moon_to(Vector2(1000, MOON_Y), 1.6)
	await _say(_moon_bubble, _moon.position + Vector2(0, -180), "Mind if I squeeze by?", 1.8)

	await _say(_sun_bubble, _sun.position + Vector2(0, -180), "Wait... what are you DOING?!", 1.8)

	_enter_rage()
	_move_moon_to(Vector2(1180, MOON_Y), 1.2)
	await _say(_sun_bubble, _sun.position + Vector2(0, -260), "GET BACK YOU PALE LITTLE ROCK!", 2.0)

	create_tween().tween_property(_sky, "color", SKY_ECLIPSED, 1.4)
	_move_moon_to(MOON_END, 1.4)
	await get_tree().create_timer(0.4).timeout
	_moon_locked = true
	_moon.texture = _moon_frames[_moon_frames.size() - 1]
	await _say(_moon_bubble, _moon.position + Vector2(0, -200), "I'm ECLIPSIIIING!", 4.0)

	# Dwell on the eclipse, then the camera drops down to the temple
	await get_tree().create_timer(1.5).timeout
	var pan := create_tween()
	pan.tween_property(_world, "position:y", -VIEW_H, 1.1).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	var blur := create_tween()
	blur.tween_property(_blur_mat, "shader_parameter/strength", 0.2, 0.45).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	blur.tween_property(_blur_mat, "shader_parameter/strength", 0.0, 0.65).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	await pan.finished

	await get_tree().create_timer(0.8).timeout
	SFX.destroy_sounds("motif")
	SFX.create_sound("motif", 0.0, 0.0, true)
	await _say(_vamp_bubble, _vamp.position + Vector2(0, -120), "An eclipse? Now I awaken!", 4.0)
	_on_back_pressed()

func _on_back_pressed() -> void:
	SFX.intro_done = true
	queue_free()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		_on_back_pressed()
