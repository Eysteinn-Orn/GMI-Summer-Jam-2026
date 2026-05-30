extends CharacterBody2D

@export var speed = 300.0
@export var jump_velocity = -500.0
@export var gravity = 1200.0
@onready var step_timer: Timer = $StepSoundTimer
var play_step : bool = true

func _physics_process(delta):

	# Gravity
	if not is_on_floor():
		velocity.y += gravity * delta

	# Jump
	if Input.is_action_just_pressed("Jump") and is_on_floor():
		velocity.y = jump_velocity
		SfxManager.destroy_sounds("vamp_jump")
		SfxManager.create_sound("vamp_jump")

	# Left / Right movement
	var direction = Input.get_axis("Left", "Right")

	if direction != 0:
		velocity.x = direction * speed
		if is_on_floor() and play_step:
			SfxManager.create_sound("step")
			play_step = false
			step_timer.start()
	else:
		velocity.x = move_toward(velocity.x, 0, speed)
	
	move_and_slide()

func _on_step_sound_timer_timeout() -> void:
	play_step = true
