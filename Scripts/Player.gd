extends CharacterBody2D

@export var speed = 300.0
@export var jump_velocity = -500.0
@export var gravity = 1200.0

func _physics_process(delta):

	# Gravity
	if not is_on_floor():
		velocity.y += gravity * delta

	# Jump
	if Input.is_action_just_pressed("Jump") and is_on_floor():
		velocity.y = jump_velocity

	# Left / Right movement
	var direction = Input.get_axis("Left", "Right")

	if direction != 0:
		velocity.x = direction * speed
	else:
		velocity.x = move_toward(velocity.x, 0, speed)

	move_and_slide()
