extends CharacterBody2D

@export var speed = 200.0
@export var jump_velocity = -500.0

@export var max_health = 10
@export var health = 10

@onready var health_bar = $"../CanvasLayer/ProgressBar"

func _ready():
	health_bar.max_value = max_health
	health_bar.value = health

func _physics_process(delta):
	var direction = Vector2(
		Input.get_axis("Left", "Right"),
		Input.get_axis("Up", "Down")
	)

	# Prevents diagonal movement, creates a more akward movement pattern.
	# if direction.x != 0 and direction.y != 0:
	# 	if abs(direction.x) >= abs(direction.y):
	# 		direction.y = 0
	# 	else:
	# 		direction.x = 0

	velocity = direction.normalized() * speed
	move_and_slide()
	
	if Input.is_action_just_pressed("Space"):
		take_damage(1)

func take_damage(amount):
	health -= amount
	health = clamp(health, 0, max_health)
	health_bar.value = health
	
func heal_damage(amount):
	health += amount
	health = clamp(health, 0, max_health)
	health_bar.value = health
