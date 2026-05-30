extends CharacterBody2D

@export var speed = 200.0
@export var jump_velocity = -500.0

func _physics_process(delta):
	var direction = Vector2(
		Input.get_axis("Left", "Right"),
		Input.get_axis("Up", "Down")
	)

	velocity = direction.normalized() * speed
	move_and_slide()


func _on_area_2d_body_entered(body: Node2D) -> void:
	pass # Replace with function body.


func _on_area_2d_body_exited(body: Node2D) -> void:
	pass # Replace with function body.
