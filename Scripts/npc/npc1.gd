extends CharacterBody2D

@export var speed := 50.0
@export var hop_height := 8.0
@export var hop_speed := 12.0
@export var travel_distance := 80.0
@export var bubble_interval := 4.0
@export var bubble_duration := 2.0
@export var drag_speed := 220.0
@export var drag_smooth_time := 0.08
@export var retarget_threshold := 2.0

@onready var animation_tree: AnimationTree = %AnimationTree
@onready var sprite: Sprite2D = $Sprite2D
@onready var bubble: Label = $Bubble
@onready var draggable_component: Draggable = get_node_or_null("Draggable")

var _origin_x := 0.0
var _dir := 1.0
var _hop_time := 0.0
var _bubble_t := 0.0
var _bubble_visible := false
var dragged_by: Node = null
var smoothed_target := Vector2.ZERO

func _ready() -> void:
	_origin_x = position.x
	smoothed_target = global_position
	bubble.visible = false

func _physics_process(delta: float) -> void:
	if dragged_by != null:
		_update_hop(delta)
		_update_bubble(delta)
		return

	if absf(position.x - _origin_x) >= travel_distance:
		_dir = -_dir
		position.x = _origin_x + signf(position.x - _origin_x) * travel_distance

	var direction := Vector2(_dir, 0.0)
	velocity = direction * speed
	var collision := move_and_collide(velocity * delta)
	if collision != null:
		_dir = -_dir

	animation_tree.set("parameters/walk/blend_position", direction)
	_update_hop(delta)
	_update_bubble(delta)

func begin_drag(by: Node) -> bool:
	if dragged_by:
		return false
	if draggable_component and not draggable_component.begin_drag(by):
		return false

	dragged_by = by
	smoothed_target = global_position
	velocity = Vector2.ZERO
	return true

func end_drag() -> void:
	if draggable_component:
		draggable_component.end_drag()
	dragged_by = null
	smoothed_target = global_position
	velocity = Vector2.ZERO

func drag_to(target: Vector2, delta: float) -> void:
	_update_smoothed_target(target, delta)

	var to_target := smoothed_target - global_position
	if to_target.length() <= 0.001:
		velocity = Vector2.ZERO
		return

	var move_step := to_target.limit_length(drag_speed * delta)
	var collision := move_and_collide(move_step)
	if collision == null:
		velocity = move_step / max(delta, 0.0001)
	else:
		velocity = Vector2.ZERO

	if to_target.length() > 0.01:
		animation_tree.set("parameters/walk/blend_position", to_target.normalized())

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

func _update_hop(delta: float) -> void:
	_hop_time += delta * hop_speed
	sprite.position.y = -absf(sin(_hop_time)) * hop_height

func _update_bubble(delta: float) -> void:
	_bubble_t += delta
	if _bubble_visible and _bubble_t >= bubble_duration:
		bubble.visible = false
		_bubble_visible = false
		_bubble_t = 0.0
	elif not _bubble_visible and _bubble_t >= bubble_interval:
		bubble.visible = true
		_bubble_visible = true
		_bubble_t = 0.0
