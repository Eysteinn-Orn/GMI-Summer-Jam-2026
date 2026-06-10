extends RigidBody2D

signal drag_released(object: RigidBody2D)

@export var drag_force := 2000.0
@export var max_speed := 160.0
@export var drag_linear_damp := 8.0
@export var drag_smooth_time := 0.08
@export var retarget_threshold := 2.0

@onready var draggable_component: Draggable = get_node_or_null("Draggable")

var dragged_by: Node = null
var smoothed_target := Vector2.ZERO
var _prev_linear_damp := 0.0

func begin_drag(by: Node) -> bool:
	if dragged_by:
		return false
	if draggable_component and not draggable_component.begin_drag(by):
		return false
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
