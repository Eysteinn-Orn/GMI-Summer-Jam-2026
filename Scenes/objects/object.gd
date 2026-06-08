extends RigidBody2D

@export var drag_force := 2000.0
@export var max_speed := 160.0
@export var drag_linear_damp := 8.0
@export var drag_smooth_time := 0.08
@export var retarget_threshold := 2.0

@onready var draggable_component: Draggable = get_node_or_null("Draggable")

var dragged_by: Node = null
var smoothed_target := Vector2.ZERO
var _target_tween: Tween

func begin_drag(by: Node) -> bool:
	if dragged_by:
		return false
	if draggable_component and not draggable_component.begin_drag(by):
		return false
	dragged_by = by
	smoothed_target = global_position
	if is_instance_valid(_target_tween):
		_target_tween.kill()
		_target_tween = null
	linear_damp = drag_linear_damp
	return true

func end_drag() -> void:
	if draggable_component:
		draggable_component.end_drag()
	dragged_by = null
	if is_instance_valid(_target_tween):
		_target_tween.kill()
		_target_tween = null
	linear_damp = 1.0

func drag_to(target: Vector2, _delta: float) -> void:
	_update_smoothed_target(target)
	var direction = smoothed_target - global_position
	var to_target = direction
	apply_central_force(to_target * drag_force)
	linear_velocity = linear_velocity.limit_length(max_speed)

func _update_smoothed_target(target: Vector2) -> void:
	if smoothed_target == Vector2.ZERO:
		smoothed_target = global_position

	if smoothed_target.distance_to(target) <= retarget_threshold:
		return

	if is_instance_valid(_target_tween):
		_target_tween.kill()

	_target_tween = create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	_target_tween.tween_property(self, "smoothed_target", target, drag_smooth_time)
