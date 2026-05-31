extends Control

var _cam: Camera3D
var _target: Node3D
var _base_distance: float
var _base_fov: float
var _dragging_dolly := false
var _dragging_angle := false
var _dolly_thumb: ColorRect
var _angle_thumb: ColorRect

func _make_thumb(parent: ColorRect) -> ColorRect:
	var thumb := ColorRect.new()
	thumb.color = Color(1, 1, 1, 0.9)
	thumb.size = Vector2(parent.size.x, 6)
	thumb.position.y = parent.size.y / 2.0 - 3
	parent.add_child(thumb)
	return thumb

func _ready() -> void:
	_cam = get_viewport().get_camera_3d()
	if _cam:
		_base_fov = _cam.fov
		var target_path = _cam.get("target")
		if target_path:
			_target = _cam.get_node_or_null(target_path)
			if _target:
				_base_distance = (_cam.global_position - _target.global_position).length()
	_dolly_thumb = _make_thumb($DollySlider)
	_angle_thumb = _make_thumb($AngleSlider)
	_update_dolly_thumb(_cam.fov if _cam else 15.0)
	_update_angle_thumb(rad_to_deg(abs(_cam.rotation.x)) if _cam else 30.0)

func _update_dolly_thumb(fov: float) -> void:
	var t := (fov - 5.0) / 85.0
	var h := ($DollySlider as ColorRect).size.y
	_dolly_thumb.position.y = (1.0 - t) * h - 3

func _update_angle_thumb(degrees: float) -> void:
	var t := (degrees - 1.0) / 89.0
	var h := ($AngleSlider as ColorRect).size.y
	_angle_thumb.position.y = (1.0 - t) * h - 3

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton and not event.pressed:
		_dragging_dolly = false
		_dragging_angle = false

	if event is InputEventMouseButton and event.pressed:
		var dolly_rect := $DollySlider as ColorRect
		var angle_rect := $AngleSlider as ColorRect
		var pos: Vector2 = event.position
		if dolly_rect.get_global_rect().has_point(pos):
			_dragging_dolly = true
		elif angle_rect.get_global_rect().has_point(pos):
			_dragging_angle = true

	if event is InputEventMouseMotion:
		if _dragging_dolly:
			var rect := ($DollySlider as ColorRect).get_global_rect()
			var t := 1.0 - clampf((event.position.y - rect.position.y) / rect.size.y, 0.05, 0.95)
			_apply_dolly_zoom(lerpf(5.0, 90.0, t))
		elif _dragging_angle:
			var rect := ($AngleSlider as ColorRect).get_global_rect()
			var t := 1.0 - clampf((event.position.y - rect.position.y) / rect.size.y, 0.05, 0.95)
			_apply_angle(lerpf(1.0, 90.0, t))

func _apply_dolly_zoom(new_fov: float) -> void:
	if not _cam or not _target:
		return
	var ratio := tan(deg_to_rad(_base_fov / 2.0)) / tan(deg_to_rad(new_fov / 2.0))
	var new_dist := _base_distance * ratio
	var dir := (_cam.global_position - _target.global_position).normalized()
	_cam.global_position = _target.global_position + dir * new_dist
	_cam.fov = new_fov
	_cam.follow_offset = _cam.global_position - _target.global_position
	_update_dolly_thumb(new_fov)

func _apply_angle(degrees: float) -> void:
	if not _cam or not _target:
		return
	var dist := (_cam.global_position - _target.global_position).length()
	var rad := deg_to_rad(degrees)
	var offset := Vector3(0, sin(rad) * dist, cos(rad) * dist)
	_cam.global_position = _target.global_position + offset
	_cam.rotation.x = -rad
	_cam.follow_offset = offset
	for sprite in get_tree().get_nodes_in_group("grounded_sprites"):
		sprite.rotation.x = -rad
		sprite.update_grounding()
	_update_angle_thumb(degrees)
