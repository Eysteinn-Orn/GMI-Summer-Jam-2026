extends CharacterBody3D

@export var speed := 210.0
@export var hop_height := 8.0
@export var hop_speed := 12.0
@onready var sprite := $Sprite3D as Sprite3D

var _hop_time := 0.0
var prev_prev_hop := 0.1
var prev_hop := 0.0

func _physics_process(delta: float) -> void:
	var dir := Vector2(
		Input.get_axis("Left", "Right"),
		Input.get_axis("Up", "Down")
	)
	velocity = Vector3(dir.x, 0, dir.y).normalized() * speed
	move_and_slide()
	if dir.length() > 0.01:
		_hop_time += delta * hop_speed
		sprite.position.y = abs(sin(_hop_time)) * hop_height
		if has_hopped():
			SFX.destroy_sounds("step")
			SFX.create_sound("step", -8.0)
		prev_prev_hop = prev_hop
		prev_hop = sprite.position.y
	else:
		_hop_time = 0.0
		sprite.position.y = 0.0
		prev_prev_hop = 0.1
		prev_hop = 0.0

func has_hopped() -> bool:
	if prev_hop >= prev_prev_hop: return false
	if sprite.position.y < prev_hop: return false
	return true
	
