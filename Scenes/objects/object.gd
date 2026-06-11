extends RigidBody2D

signal drag_released(object: RigidBody2D)

const SPACEBAR_ICON := preload("res://Assets/10k Game Assets/Pixel Art (4770)/Control Prompts (628)/Light (314)/keyboard_space_2.png")

@export var drag_force := 2000.0
@export var max_speed := 160.0
@export var drag_linear_damp := 8.0
@export var drag_smooth_time := 0.08
@export var retarget_threshold := 2.0
@export var focus_highlight_color := Color(1.0, 0.95, 0.55, 1.0)
@export var focus_highlight_blend := 0.5
@export var focus_prompt_offset := Vector2(0.0, -12.0)
@export var focus_prompt_scale := Vector2.ONE
@onready var draggable_component: Draggable = get_node_or_null("Draggable")
@onready var sprite: Sprite2D = get_node_or_null("Sprite2D")

var dragged_by: Node = null
var smoothed_target := Vector2.ZERO
var _prev_linear_damp := 0.0
var _is_drag_focused := false
var _base_sprite_modulate := Color.WHITE
var _focus_prompt: Sprite2D = null
var registered : bool = false

func _process(_delta : float) -> void:
	if registered:
		for child in get_children():
			if child is Sprite2D and child.name != "Sprite2D":
				child.queue_free()

func _ready() -> void:
	if sprite:
		_base_sprite_modulate = sprite.modulate
	_focus_prompt = Sprite2D.new()
	_focus_prompt.texture = SPACEBAR_ICON
	_focus_prompt.position = focus_prompt_offset
	_focus_prompt.scale = focus_prompt_scale
	_focus_prompt.z_index = 10
	_focus_prompt.visible = false
	add_child(_focus_prompt)

func begin_drag(by: Node) -> bool:
	if dragged_by or registered:
		return false
	if draggable_component and not draggable_component.begin_drag(by):
		return false
	set_drag_focus(false)
	SFX.destroy_sounds("key_up")
	SFX.create_sound("key_up")
	dragged_by = by
	smoothed_target = global_position
	_prev_linear_damp = linear_damp
	linear_damp = drag_linear_damp
	return true

func end_drag() -> void:
	if draggable_component:
		SFX.destroy_sounds("key_down")
		SFX.create_sound("key_down")
		draggable_component.end_drag()
	dragged_by = null
	if _prev_linear_damp > 0.0:
		linear_damp = _prev_linear_damp
		_prev_linear_damp = 0.0
	drag_released.emit(self)

func drag_to(target: Vector2, delta: float) -> void:
	_update_smoothed_target(target, delta)
	var direction = smoothed_target - global_position
	var to_target = direction
	apply_central_force(to_target * drag_force)
	linear_velocity = linear_velocity.limit_length(max_speed)

func _update_smoothed_target(target: Vector2, delta: float) -> void:
	if smoothed_target == Vector2.ZERO:
		smoothed_target = global_position

	if smoothed_target.distance_to(target) <= retarget_threshold:
		return

	if drag_smooth_time <= 0.0:
		smoothed_target = target
		return

	var alpha := 1.0 - exp(-delta / drag_smooth_time)
	smoothed_target = smoothed_target.lerp(target, clamp(alpha, 0.0, 1.0))

func set_drag_focus(is_focused: bool) -> void:
	var should_focus := is_focused and dragged_by == null
	if _is_drag_focused == should_focus:
		return

	_is_drag_focused = should_focus
	if sprite:
		if _is_drag_focused:
			sprite.modulate = _base_sprite_modulate.lerp(focus_highlight_color, clamp(focus_highlight_blend, 0.0, 1.0))
		else:
			sprite.modulate = _base_sprite_modulate

	if _focus_prompt:
		_focus_prompt.visible = _is_drag_focused
