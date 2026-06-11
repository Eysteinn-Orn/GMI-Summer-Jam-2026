class_name DragInteractor
extends Node

@export var body: CharacterBody2D
@export var grab_area: Area2D
@export var drag_anchor: Node2D
@export var interact_action := "interact"
@export var min_follow_distance := 10.0
@export var grab_distance := 14.0
@export var move_threshold := 0.01
@export var rotate_grab_area := true

var current: Node = null
var _last_facing_dir := Vector2.DOWN
var _focused_candidates: Array[Node] = []

func _ready() -> void:
	assert(body and grab_area and drag_anchor)

func _physics_process(delta: float) -> void:
	if Input.is_action_pressed(interact_action):
		if current == null:
			_try_grab()
	elif current != null:
		_release()

	_update_drag_focus_candidates()

	_update_facing_targets()

	if current and current.has_method("drag_to"):
		current.drag_to(drag_anchor.global_position, delta)

func _exit_tree() -> void:
	_clear_drag_focus()

func _try_grab() -> void:
	var best: Node = null
	var best_dist := INF
	for b in grab_area.get_overlapping_bodies():
		if b == body:
			continue
		if b.has_method("begin_drag"):
			var d := body.global_position.distance_to(b.global_position)
			if d < best_dist:
				best_dist = d
				best = b
	if best and best.begin_drag(body):
		current = best

func _release() -> void:
	if current and current.has_method("end_drag"):
		current.end_drag()
	current = null

func _update_drag_focus_candidates() -> void:
	if current != null:
		_clear_drag_focus()
		return

	var next_focused: Array[Node] = []
	for candidate in grab_area.get_overlapping_bodies():
		if candidate == body:
			continue
		if not candidate.has_method("begin_drag"):
			continue

		next_focused.append(candidate)
		if not _focused_candidates.has(candidate) and candidate.has_method("set_drag_focus"):
			candidate.set_drag_focus(true)

	for previous in _focused_candidates:
		if previous == null:
			continue
		if not next_focused.has(previous) and previous.has_method("set_drag_focus"):
			previous.set_drag_focus(false)

	_focused_candidates = next_focused

func _clear_drag_focus() -> void:
	for previous in _focused_candidates:
		if previous and previous.has_method("set_drag_focus"):
			previous.set_drag_focus(false)
	_focused_candidates.clear()

func _update_facing_targets() -> void:
	if body.velocity.length() > move_threshold:
		_last_facing_dir = body.velocity.normalized()

	var follow_target := body.global_position
	if current is Node2D and min_follow_distance > 0.0:
		var held_offset := (current as Node2D).global_position - body.global_position
		if held_offset.length() <= 0.001:
			held_offset = _last_facing_dir
		follow_target += held_offset.normalized() * min_follow_distance

	drag_anchor.global_position = follow_target
	grab_area.global_position = body.global_position + (_last_facing_dir * grab_distance)

	if rotate_grab_area:
		grab_area.global_rotation = _last_facing_dir.angle()
