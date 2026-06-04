extends CharacterBody2D

var _hop_time := 0.0
var prev_prev_hop := 0.1
var prev_hop := 0.0

@export var speed = 200.0
@export var jump_velocity = -500.0
@export var hop_height := 8.0
@export var hop_speed := 12.0
@export var max_health = 10
@export var health = 10

@onready var sprite: Sprite2D = $Sprite2D
@onready var health_bar = $"../CanvasLayer/ProgressBar"

func _ready():
	health_bar.max_value = max_health
	health_bar.value = health

func _physics_process(delta):
	var direction = Vector2(
		Input.get_axis("Left", "Right"),
		Input.get_axis("Up", "Down")
	)

	velocity = direction.normalized() * speed
	move_and_slide()
	
	if Input.is_action_just_pressed("Space"):
		take_damage(1)
	
	if direction.length() > 0.01:
		_hop_time += delta * hop_speed
		sprite.position.y = -abs(sin(_hop_time)) * hop_height
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

func take_damage(amount):
	health -= amount
	health = clamp(health, 0, max_health)
	health_bar.value = health
	
func heal_damage(amount):
	health += amount
	health = clamp(health, 0, max_health)
	health_bar.value = health
