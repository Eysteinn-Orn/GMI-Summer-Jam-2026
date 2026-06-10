extends Node

signal key_count_changed(collected: int, required: int)
signal timer_changed(time_left: float, total_time: float)
signal game_won
signal game_lost(reason: String)

enum GameState {
	RUNNING,
	WON,
	LOST,
}

@export_range(1.0, 1800.0, 1.0) var total_time: float = 90.0
@export_range(1, 64, 1) var required_keys: int = 4
@export_range(1.0, 1000.0, 1.0) var collection_radius: float = 56.0

@export var player_path: NodePath
@export var ui_path: NodePath
@export var keys_container_path: NodePath
@export var goal_marker_path: NodePath

@export_file("*.tscn") var win_scene_path: String = "res://menus/scenes/end_game/victory.tscn"
@export_file("*.tscn") var lose_scene_path: String = "res://menus/scenes/end_game/game_over.tscn"

var state: GameState = GameState.RUNNING
var time_left: float = 0.0
var collected_keys: int = 0

var _player: Node = null
var _ui: Node = null
var _keys_container: Node = null
var _goal_marker: Node2D = null
var _collected_key_ids: Dictionary = {}
var _registered_keys: Array[RigidBody2D] = []

func _ready() -> void:
	time_left = total_time
	_player = get_node_or_null(player_path)
	_ui = get_node_or_null(ui_path)
	_keys_container = get_node_or_null(keys_container_path)
	_goal_marker = get_node_or_null(goal_marker_path) as Node2D
	_register_keys()
	_seed_center_keys_as_collected()
	call_deferred("_emit_ui_state")

func _process(delta: float) -> void:
	if state != GameState.RUNNING:
		return

	if _is_player_dead():
		_lose_game("health")
		return

	time_left = maxf(0.0, time_left - delta)
	timer_changed.emit(time_left, total_time)
	if _ui and _ui.has_method("update_time_state"):
		_ui.update_time_state(time_left, total_time)

	if is_zero_approx(time_left):
		_lose_game("time")

func _register_keys() -> void:
	_registered_keys.clear()
	if not _keys_container:
		push_warning("GameManager: keys_container_path is not configured.")
		return

	for child in _keys_container.get_children():
		if not child is RigidBody2D:
			continue
		if not child.has_signal("drag_released"):
			continue

		var key := child as RigidBody2D
		_registered_keys.append(key)
		if not key.drag_released.is_connected(_on_key_drag_released):
			key.drag_released.connect(_on_key_drag_released)

func _seed_center_keys_as_collected() -> void:
	collected_keys = 0
	_collected_key_ids.clear()
	for key in _registered_keys:
		if _is_in_goal_radius(key.global_position):
			_mark_key_collected(key)

func _on_key_drag_released(key: RigidBody2D) -> void:
	if state != GameState.RUNNING:
		return
	_try_collect_key(key)

func _try_collect_key(key: RigidBody2D) -> void:
	if not is_instance_valid(key):
		return
	var key_id := key.get_instance_id()
	if _collected_key_ids.has(key_id):
		return
	if not _is_in_goal_radius(key.global_position):
		return

	_mark_key_collected(key)
	_emit_ui_state()

	if collected_keys >= required_keys:
		_win_game()

func _mark_key_collected(key: RigidBody2D) -> void:
	var key_id := key.get_instance_id()
	_collected_key_ids[key_id] = true
	collected_keys += 1

func _is_in_goal_radius(position: Vector2) -> bool:
	return position.distance_to(_get_goal_position()) <= collection_radius

func _get_goal_position() -> Vector2:
	if is_instance_valid(_goal_marker):
		return _goal_marker.global_position
	return Vector2.ZERO

func _is_player_dead() -> bool:
	if not _player:
		return false
	var health = _player.get("health")
	if health is int or health is float:
		return health <= 0
	return false

func _emit_ui_state() -> void:
	key_count_changed.emit(collected_keys, required_keys)
	timer_changed.emit(time_left, total_time)
	if _ui and _ui.has_method("set_keys_progress"):
		_ui.set_keys_progress(collected_keys, required_keys)
	if _ui and _ui.has_method("update_time_state"):
		_ui.update_time_state(time_left, total_time)

func _win_game() -> void:
	if state != GameState.RUNNING:
		return
	state = GameState.WON
	game_won.emit()
	if _ui and _ui.has_method("show_end_state"):
		_ui.show_end_state("VICTORY")
	_transition_to_outcome(win_scene_path)

func _lose_game(reason: String) -> void:
	if state != GameState.RUNNING:
		return
	state = GameState.LOST
	game_lost.emit(reason)
	if _ui and _ui.has_method("show_end_state"):
		_ui.show_end_state("GAME OVER")
	_transition_to_outcome(lose_scene_path)

func _transition_to_outcome(scene_path: String) -> void:
	if scene_path.is_empty():
		return
	if not has_node("/root/SceneLoader"):
		push_warning("GameManager: SceneLoader autoload was not found; cannot load outcome scene.")
		return
	SceneLoader.load_scene(scene_path)
