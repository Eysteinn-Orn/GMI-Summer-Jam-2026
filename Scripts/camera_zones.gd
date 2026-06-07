extends Node2D

@export var player : Node
@onready var zones : Dictionary[int, Node] = {
	1 : $Zone1, 2 : $Zone2, 3 : $Zone3,
	4 : $Zone4, 5 : $Zone5, 6 : $Zone6,
	7 : $Zone7, 8 : $Zone8, 9 : $Zone9
}
@onready var active_camera : Camera2D = zones[5]
const camera_size     : Vector2 = Vector2(480, 270)
const camera_offset_y : float   = 202

func set_active_camera(i : int) -> void:
	active_camera.enabled = false
	zones[i].enabled = true
	active_camera = zones[i]

func _physics_process(_delta: float) -> void:
	var focus : Vector2 = player.position
	if focus.y < -camera_size.y/2:
		if focus.x < -camera_size.x/2:
			set_active_camera(1)
		elif focus.x > camera_size.x/2:
			set_active_camera(3)
		else:
			set_active_camera(2)
	elif focus.y > camera_size.y/2 - camera_offset_y/4:
		if focus.x < -camera_size.x/2:
			set_active_camera(7)
		elif focus.x > camera_size.x/2:
			set_active_camera(9)
		else:
			set_active_camera(8)
	else:
		if focus.x < -camera_size.x/2:
			set_active_camera(4)
		elif focus.x > camera_size.x/2:
			set_active_camera(6)
		else:
			set_active_camera(5)
			
			
			
			
			
			
			
			
			
			
			
			
