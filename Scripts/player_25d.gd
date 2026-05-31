extends CharacterBody3D

@export var speed := 210.0
@export var hop_height := 8.0
@export var hop_speed := 12.0

var _hop_time := 0.0

func _physics_process(delta: float) -> void:
	var dir := Vector2(
		Input.get_axis("Left", "Right"),
		Input.get_axis("Up", "Down")
	)
	velocity = Vector3(dir.x, 0, dir.y).normalized() * speed
	move_and_slide()
	var sprite := $Sprite3D as Sprite3D
	if dir.length() > 0.01:
		_hop_time += delta * hop_speed
		sprite.position.y = abs(sin(_hop_time)) * hop_height
	else:
		_hop_time = 0.0
		sprite.position.y = 0.0
