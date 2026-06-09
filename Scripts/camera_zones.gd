extends Camera2D

## assumes value of zoom = Vector2(4.0, 4.0)
@export var camera_grid : TextureRect
@export var player : Node
const camera_size : Vector2 = Vector2(480, 270)
const hud_height  : float   = 202
const bounds_size : Vector2 = Vector2(camera_size.x, camera_size.y - hud_height/4)
const offset_y    : float   = - hud_height / 8
const SPEED = 1000.0

func _ready() -> void:
	camera_grid.visible = false

func get_camera_pos(focus: Vector2) -> Vector2:
	var camera_index : Vector2 = Vector2(
		ceil((focus.x - (camera_size.x/2)) / bounds_size.x),
		ceil((focus.y - (camera_size.y/2) + (hud_height/4)) / bounds_size.y)
	)
	return Vector2(
		camera_index.x * bounds_size.x,
		camera_index.y * bounds_size.y
	)

func _process(delta: float) -> void:
	position = Vector2(
		move_toward(position.x, get_camera_pos(player.position).x, delta * SPEED),
		move_toward(position.y, get_camera_pos(player.position).y, delta * SPEED)
	)
