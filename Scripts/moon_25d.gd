extends CharacterBody3D

@export var speed := 125.0

func _physics_process(_delta: float) -> void:
	var dir := Vector2(
		Input.get_axis("Left2", "Right2"),
		Input.get_axis("Up2", "Down2")
	)
	velocity = Vector3(dir.x, 0, dir.y).normalized() * speed
	move_and_slide()
